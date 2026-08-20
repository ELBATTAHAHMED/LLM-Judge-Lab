from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from main import controlled_results  # noqa: E402


def test_controlled_endpoint_returns_explicit_empty_state_in_isolated_database(tmp_path):
    path = tmp_path / "phase7.sqlite"
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{path.as_posix()}")
    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    with sessionmaker(bind=engine)() as session:
        response = controlled_results(session)
    assert response.status == "NO_CONTROLLED_EVIDENCE"
    assert response.evidence_class == "CONTROLLED"
    assert response.executed_runs == response.executed_passes == 0
    assert response.results == []


def test_final_views_have_explicit_evidence_contract_and_no_mock_fallback():
    source = (ROOT / "frontend" / "src" / "components" / "ControlledEvidencePanel.tsx").read_text(encoding="utf-8")
    contract = (ROOT / "frontend" / "src" / "api" / "evidence.ts").read_text(encoding="utf-8")
    assert "NO CONTROLLED EVIDENCE" in source
    assert "LEGACY_EXPLORATORY" in contract and "DRY_RUN_MOCK" in contract
    assert "value?.evidence_class === 'CONTROLLED'" in contract
