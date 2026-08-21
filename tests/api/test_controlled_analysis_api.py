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

from controlled_analysis_adapter import rq1_from_run
from controlled_analysis_publisher import publish_analysis_run
from controlled_models import Experiment, ExperimentManifest
from controlled_evaluation import ControlledEvaluationEngine, ControlledExecutionService
from main import app
from database import get_db
from mock_provider import DeterministicMockProvider, MockScenario
from controlled_analysis_metrics import analyze_rq1
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
    monkeypatch.setattr(main, "call_judge", lambda **_: calls.append(True))
    response = TestClient(app).post("/api/evaluate", json={"prompt": "q", "answer_a": "a", "answer_b": "b"})
    assert response.status_code == 403 and calls == []
