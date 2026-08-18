"""Opt-in disposable PostgreSQL E2E for RQ6 and AnalysisRun/API provenance."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from controlled_analysis_adapter import rq1_from_run, rq6_from_run
from controlled_analysis_publisher import publish_analysis_run
from controlled_evaluation import ControlledEvaluationEngine, ControlledExecutionService
from controlled_models import Experiment, ExperimentManifest
from database import get_db
from main import app
from mock_provider import DeterministicMockProvider, MockScenario
from phase4_metrics import analyze_rq1, analyze_rq6
from test_phase5_offline_integration import chain, request


@pytest.mark.skipif(not os.getenv("PHASE85_POSTGRES_E2E_URL"), reason="explicit disposable PostgreSQL E2E URL not configured")
def test_postgres_rq6_and_analysisrun_api_e2e():
    url = os.environ["PHASE85_POSTGRES_E2E_URL"]
    cfg = Config(str(ROOT / "alembic.ini")); cfg.set_main_option("script_location", str(ROOT / "alembic")); cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "0007_pass_attempt_ledger")
    engine = create_engine(url)
    Session = sessionmaker(bind=engine)
    try:
        with Session.begin() as db:
            repo, a_slot, _, a, b = chain(db, rq="RQ6", repetition=1)
            a_slot.presentation_order = "SELF_A"; a_slot.answer_a_author_id = "gpt-4"; a_slot.answer_b_author_id = "claude-v1"
            run_a = ControlledExecutionService(repo, ControlledEvaluationEngine(DeterministicMockProvider([MockScenario.ANSWER_A]))).execute_single(unit=a_slot, request=request(a_slot, a, b), idempotency_key="a" * 64)
            repo, b_slot, _, a2, b2 = chain(db, rq="RQ6", repetition=2)
            b_slot.presentation_order = "SELF_B"; b_slot.answer_a_author_id = "claude-v1"; b_slot.answer_b_author_id = "gpt-4"
            run_b = ControlledExecutionService(repo, ControlledEvaluationEngine(DeterministicMockProvider([MockScenario.ANSWER_A]))).execute_single(unit=b_slot, request=request(b_slot, a2, b2), idempotency_key="b" * 64)
            metric = analyze_rq6([rq6_from_run(run_a, a_slot), rq6_from_run(run_b, b_slot)], iterations=20)["self_family_preference"]
            assert metric.value == 0.5 and run_a.passes[0].presented_answer_a_id == a_slot.answer_a_id and run_b.passes[0].presented_answer_b_id == b_slot.answer_b_id

            repo, unit, _, ra, rb = chain(db, rq="RQ1", repetition=7)
            run = ControlledExecutionService(repo, ControlledEvaluationEngine(DeterministicMockProvider([MockScenario.ANSWER_A]))).execute_single(unit=unit, request=request(unit, ra, rb), idempotency_key="c" * 64)
            analysis = publish_analysis_run(session=db, experiment=db.get(Experiment, unit.experiment_id), manifest=db.get(ExperimentManifest, unit.manifest_id), rq_code="RQ1", metrics=analyze_rq1([rq1_from_run(run, unit)], iterations=20), source_units=[unit], analysis_seed=20260818)
            analysis_id = str(analysis.id)
        def override_db():
            with Session() as db:
                yield db
        app.dependency_overrides[get_db] = override_db
        response = TestClient(app).get("/api/controlled/results")
        app.dependency_overrides.clear()
        row = response.json()["results"][0]
        assert response.status_code == 200 and row["evidence_class"] == "CONTROLLED" and row["analysis_version"] == "phase4-analysis-v1" and analysis_id
    finally:
        app.dependency_overrides.clear(); engine.dispose()
