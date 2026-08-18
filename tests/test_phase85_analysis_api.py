"""Post-persistence controlled analysis and populated API contract."""
from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from controlled_analysis_adapter import rq1_from_run
from controlled_analysis_publisher import publish_analysis_run
from controlled_models import Experiment, ExperimentManifest
from controlled_evaluation import ControlledEvaluationEngine, ControlledExecutionService
from main import app
from database import get_db
from mock_provider import DeterministicMockProvider, MockScenario
from phase4_metrics import analyze_rq1
from test_phase5_offline_integration import chain, request


def test_controlled_analysisrun_and_populated_api_use_persisted_evidence(tmp_path):
    path = tmp_path / "analysis.sqlite"
    cfg = Config(str(ROOT / "alembic.ini")); cfg.set_main_option("script_location", str(ROOT / "alembic")); cfg.set_main_option("sqlalchemy.url", f"sqlite:///{path.as_posix()}")
    command.upgrade(cfg, "0007_pass_attempt_ledger")
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
        assert response.status_code == 200 and body["status"] == "CONTROLLED_RESULTS_AVAILABLE"
        row = body["results"][0]
        required = {"rq", "judge", "condition", "metric", "value", "numerator", "denominator", "eligible_n", "analyzed_n", "ties", "unknowns", "failures", "excluded", "ci_low", "ci_high", "status", "analysis_version", "evidence_class"}
        assert required <= set(row) and row["evidence_class"] == "CONTROLLED" and analysis_id
    finally:
        app.dependency_overrides.clear(); engine.dispose()
