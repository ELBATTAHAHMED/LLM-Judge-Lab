from __future__ import annotations

import sys
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from controlled_models import ControlledRun, ExperimentalUnit, RunPass  # noqa: E402
from controlled_runner import ControlledRunner, ExecutionProfile, MOCK_EVIDENCE_CLASS  # noqa: E402
from experiment_planning import PairRecord  # noqa: E402


@pytest.fixture()
def isolated_engine(tmp_path):
    path = tmp_path / "phase6.sqlite"; cfg = Config(str(ROOT / "alembic.ini")); cfg.set_main_option("script_location", str(ROOT / "alembic")); cfg.set_main_option("sqlalchemy.url", f"sqlite:///{path.as_posix()}")
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{path.as_posix()}"); event.listen(engine, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))
    try: yield engine
    finally: engine.dispose()


def real_shape_pairs(count=12):
    models = (("gpt-4", "claude-v1"), ("claude-v1", "llama-13b"), ("llama-13b", "gpt-4"))
    return [PairRecord(i, i // 2, i * 10 + 1, i * 10 + 2, f"Answer A {i}", f"Answer B {i}", *models[i % 3], "writing", ("ANSWER_A", "ANSWER_B", "TIE")[i % 3]) for i in range(1, count + 1)]


def test_full_mock_rehearsal_persists_analyzes_serializes_and_exports(isolated_engine, tmp_path):
    runner = ControlledRunner(ExecutionProfile(base_unit_limit=4, bootstrap_iterations=40)); pairs = real_shape_pairs()
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        rehearsal = runner.dry_run(session, pairs, snapshot_id="real-shape-frozen")
        assert rehearsal["evidence_class"] == MOCK_EVIDENCE_CLASS and all(not runner.validate({rq: [item[3] for item in rows]}) for rq, rows in rehearsal["runs"].items())
        assert sum(item["runs"] for item in rehearsal["status"].values()) == sum(summary.planned_units for summary in rehearsal["plans"].values())
        assert sum(item["passes"] for item in rehearsal["status"].values()) == sum(summary.planned_calls for summary in rehearsal["plans"].values())
        analysis_a = runner.analyze(rehearsal); analysis_b = runner.analyze(rehearsal)
        assert set(analysis_a) == {f"RQ{i}" for i in range(1, 8)} and analysis_a == analysis_b
        for rq, metrics in analysis_a.items():
            for metric in metrics.values():
                required_contract = {"rq", "judge", "condition", "metric", "value", "numerator", "denominator", "eligible_n", "analyzed_n", "ties", "unknowns", "failures", "excluded", "ci_low", "ci_high", "status", "analysis_version", "evidence_class"}
                assert metric["evidence_class"] == MOCK_EVIDENCE_CLASS and required_contract <= set(metric)
        export = runner.export(analysis_a, tmp_path / "dry-run" / "controlled_results.json")
        assert export.exists() and MOCK_EVIDENCE_CLASS in export.read_text(encoding="utf-8")
        assert session.query(ControlledRun).count() == sum(summary.planned_units for summary in rehearsal["plans"].values())
        assert session.query(RunPass).count() == sum(summary.planned_calls for summary in rehearsal["plans"].values())


def test_active_plan_reconciles_without_pricing_guess():
    pairs = real_shape_pairs(600); runner = ControlledRunner()
    plans, summaries = runner.plan(pairs, snapshot_id="frozen-full")
    assert not runner.validate(plans) and sum(s.planned_calls for s in summaries.values()) == 12_600
    preflight = runner.preflight(pairs, snapshot_id="frozen-full")
    assert sum(int(row["planned_calls"]) for row in preflight.values()) == 12_600
    assert all(row["pricing"] == "PRICING VERIFICATION REQUIRED" and int(row["estimated_input_tokens"]) > 0 and int(row["estimated_output_tokens"]) > 0 for row in preflight.values())


def test_execution_gate_budget_guard_idempotency_and_status_are_safe(isolated_engine):
    runner = ControlledRunner(ExecutionProfile(base_unit_limit=2, bootstrap_iterations=20)); pairs = real_shape_pairs(6); Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        first = runner.dry_run(session, pairs, snapshot_id="idempotent")
        runs_before, passes_before = session.query(ControlledRun).count(), session.query(RunPass).count()
        second = runner.dry_run(session, pairs, snapshot_id="idempotent")
        assert session.query(ControlledRun).count() == runs_before and session.query(RunPass).count() == passes_before
        assert first["status"] == second["status"]
    with pytest.raises(PermissionError): runner.execute_real()
    with pytest.raises(ValueError): runner.enforce_budget(calls=2, tokens=1, max_calls=1, max_tokens=2)
    with pytest.raises(ValueError): runner.enforce_budget(calls=1, tokens=1, max_calls=2, max_tokens=2, max_usd_budget=1.0)


def test_active_protocol_mock_rehearsal_reconciles_without_provider_calls(isolated_engine):
    """Uses production data read-only and persists only into pytest's SQLite DB."""
    from database import SessionLocal
    from experiment_planning import database_pairs

    with SessionLocal() as source_session:
        pairs = database_pairs(source_session)
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        rehearsal = ControlledRunner(ExecutionProfile(bootstrap_iterations=10)).dry_run(session, pairs, snapshot_id="live-db-0004-frozen")
        assert sum(summary.planned_calls for summary in rehearsal["plans"].values()) == 12_600
        assert sum(status["passes"] for status in rehearsal["status"].values()) == 12_600
        # The active protocol has a single RQ2 baseline condition. The frozen
        # Phase 11 package retains its historical 16,600-slot evidence record.
        assert session.query(ControlledRun).count() == 9_400
        assert session.query(RunPass).count() == 12_600
        counters = rehearsal["transport_counters"]
        assert counters["provider_bound_requests"] >= 12_600
        assert all(counters["models"][model] >= expected for model, expected in {"gpt-4o-mini": 3200, "anthropic/claude-3-haiku": 3200, "deepseek/deepseek-chat": 3000, "meta-llama/llama-3.3-70b-instruct": 3200}.items())
        assert counters["upstreams"] == {"amazon-bedrock": counters["models"]["anthropic/claude-3-haiku"], "streamlake": counters["models"]["deepseek/deepseek-chat"], "deepinfra/turbo": counters["models"]["meta-llama/llama-3.3-70b-instruct"]}
        rerun = ControlledRunner(ExecutionProfile(bootstrap_iterations=10)).dry_run(session, pairs, snapshot_id="live-db-0004-frozen")
        assert session.query(ControlledRun).count() == 9_400
        assert session.query(RunPass).count() == 12_600
        assert rerun["status"] == rehearsal["status"]
