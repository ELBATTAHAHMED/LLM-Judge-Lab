"""Post-persistence controlled analysis and populated API contract."""
from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from backend.analysis.adapter import rq1_from_run
from backend.analysis.publisher import publish_analysis_run
from backend.core.controlled_models import Experiment, ExperimentManifest
from backend.evaluation.engine import ControlledEvaluationEngine, ControlledExecutionService
from main import app
from backend.core.database import get_db
from backend.evaluation.mock import DeterministicMockProvider, MockScenario
from backend.analysis.metrics import analyze_rq1
from tests.integration.test_offline_integration import chain, request


def test_noncanonical_controlled_analysisrun_cannot_replace_final_evidence(tmp_path):
    path = tmp_path / "analysis.sqlite"
    cfg = Config(str(ROOT / "alembic.ini")); cfg.set_main_option("script_location", str(ROOT / "alembic")); cfg.set_main_option("sqlalchemy.url", f"sqlite:///{path.as_posix()}")
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    Session = sessionmaker(bind=engine)
    try:
        with Session.begin() as db:
            repo, unit, _, a, b = chain(db, rq="RQ1")
            run = ControlledExecutionService(repo, ControlledEvaluationEngine(DeterministicMockProvider([MockScenario.ANSWER_A]))).execute_single(unit=unit, request=request(unit, a, b), idempotency_key="b" * 64)
            metric = analyze_rq1([rq1_from_run(run, unit)], iterations=20)
            published = publish_analysis_run(session=db, experiment=db.get(Experiment, unit.experiment_id), manifest=db.get(ExperimentManifest, unit.manifest_id), rq_code="RQ1", metrics=metric, source_units=[unit], analysis_seed=20260818)
            analysis_id = str(published.id)
        def override_db():
            with Session() as db:
                yield db
        app.dependency_overrides[get_db] = override_db
        response = TestClient(app).get("/api/controlled/results")
        app.dependency_overrides.clear()
        body = response.json()
        assert response.status_code == 200 and body["status"] == "CONTROLLED_RESULTS_PENDING_ANALYSIS"
        assert body["results"] == [] and analysis_id not in body["analysis_runs"].values()
        assert body["accounting"] == {
            "planned_units": 1, "succeeded_units": 1, "valid_partial_units": 0,
            "failed_units": 0, "pending_units": 0, "planned_pass_slots": 1,
            "valid_returned_passes": 1, "failed_pass_slots": 0,
            "provider_error_pass_slots": 0, "invalid_response_pass_slots": 0,
            "paired_excluded_valid_pass_slots": 0,
        }
        assert "Canonical final AnalysisRun records are missing" in body["message"]
    finally:
        app.dependency_overrides.clear(); engine.dispose()


def test_live_sandbox_provider_routes_are_disabled_before_transport(monkeypatch):
    import main
    calls = []
    monkeypatch.setenv("ENABLE_LIVE_SANDBOX_PROVIDER_CALLS", "false")
    monkeypatch.setattr(main, "call_judge", lambda **_: calls.append("standard"))
    monkeypatch.setattr(main, "call_calibrated_judge", lambda **_: calls.append("calibrated"))
    monkeypatch.setattr(main, "call_multi_judge_ensemble", lambda **_: calls.append("ensemble"))
    client = TestClient(app)
    responses = [
        client.post("/api/evaluate", json={"prompt": "q", "answer_a": "a", "answer_b": "b"}),
        client.post("/api/evaluate/calibrated", json={"question": "q", "answer_a": "a", "answer_b": "b"}),
        client.post("/api/evaluate/ensemble", json={"question": "q", "answer_a": "a", "answer_b": "b", "judge_models": ["gpt-4o-mini"]}),
    ]
    assert [response.status_code for response in responses] == [403, 403, 403]
    assert calls == []


def test_live_sandbox_status_reports_only_the_server_opt_in(monkeypatch):
    monkeypatch.setenv("ENABLE_LIVE_SANDBOX_PROVIDER_CALLS", "false")
    assert TestClient(app).get("/api/live-sandbox/status").json() == {"enabled": False}
    monkeypatch.setenv("ENABLE_LIVE_SANDBOX_PROVIDER_CALLS", "true")
    assert TestClient(app).get("/api/live-sandbox/status").json() == {"enabled": True}


def test_live_sandbox_env_gate_allows_a_route_without_a_token_header(monkeypatch):
    import main

    class FakeDatabase:
        def begin_nested(self):
            from contextlib import nullcontext
            return nullcontext()

        def commit(self):
            pass

    monkeypatch.setenv("ENABLE_LIVE_SANDBOX_PROVIDER_CALLS", "true")
    monkeypatch.setattr(main, "_validate_api_key_or_raise", lambda _model: None)
    monkeypatch.setattr(main, "call_judge", lambda **_: type("Result", (), {"verdict": "A", "reasoning": "mocked"})())
    monkeypatch.setattr(main, "_get_or_create_prompt", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(main, "_insert_answer_safe", lambda *_args, **_kwargs: 2)
    monkeypatch.setattr(main, "_insert_decision_safe", lambda *_args, **_kwargs: None)

    def override_db():
        yield FakeDatabase()

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).post("/api/evaluate", json={"prompt": "q", "answer_a": "a", "answer_b": "b", "model_name": "gpt-4o-mini"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["winner"] == "A"
