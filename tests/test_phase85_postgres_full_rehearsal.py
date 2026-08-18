"""Explicit full-scale PostgreSQL mock rehearsal; opt-in target URL only."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from controlled_models import ControlledRun, PassAttempt, RunPass
from controlled_runner import ControlledRunner, ExecutionProfile
from database import SessionLocal
from phase3_planning import database_pairs


@pytest.mark.skipif(not os.getenv("PHASE85_FULL_POSTGRES_URL"), reason="explicit disposable PostgreSQL rehearsal URL not configured")
def test_full_16600_postgres_rehearsal_and_second_run_idempotency():
    url = os.environ["PHASE85_FULL_POSTGRES_URL"]
    cfg = Config(str(ROOT / "alembic.ini")); cfg.set_main_option("script_location", str(ROOT / "alembic")); cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "0007_pass_attempt_ledger")
    with SessionLocal() as source:
        pairs = database_pairs(source)
    engine = create_engine(url, pool_pre_ping=True)
    try:
        Session = sessionmaker(bind=engine)
        with Session.begin() as db:
            runner = ControlledRunner(ExecutionProfile(bootstrap_iterations=10))
            first = runner.dry_run(db, pairs, snapshot_id="phase85f-live-frozen")
            assert sum(row.planned_calls for row in first["plans"].values()) == 16_600
            assert db.query(ControlledRun).count() == 13_400
            assert db.query(RunPass).count() == 16_600
            calls_before = db.query(PassAttempt).count()
            second = runner.dry_run(db, pairs, snapshot_id="phase85f-live-frozen")
            assert db.query(ControlledRun).count() == 13_400
            assert db.query(RunPass).count() == 16_600
            assert db.query(PassAttempt).count() == calls_before
            assert first["status"] == second["status"]
    finally:
        engine.dispose()
