"""RQ6 self-family physical-slot → pass ledger → authoritative metric E2E."""
from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from controlled_analysis_adapter import rq6_from_run
from controlled_evaluation import ControlledEvaluationEngine, ControlledExecutionService
from mock_provider import DeterministicMockProvider, MockScenario
from controlled_analysis_metrics import analyze_rq6
from tests.integration.test_offline_integration import chain, request


def test_rq6_self_a_and_self_b_are_physical_slots_and_analyze(tmp_path):
    path = tmp_path / "rq6.sqlite"
    cfg = Config(str(ROOT / "alembic.ini")); cfg.set_main_option("script_location", str(ROOT / "alembic")); cfg.set_main_option("sqlalchemy.url", f"sqlite:///{path.as_posix()}")
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    try:
        with sessionmaker(bind=engine).begin() as db:
            # GPT-family answer is physically presented in slot A and wins.
            repo, first, _, a, b = chain(db, rq="RQ6", repetition=1)
            first.presentation_order = "SELF_A"; first.answer_a_author_id = "gpt-4"; first.answer_b_author_id = "claude-v1"
            run_a = ControlledExecutionService(repo, ControlledEvaluationEngine(DeterministicMockProvider([MockScenario.ANSWER_A]))).execute_single(unit=first, request=request(first, a, b), idempotency_key="1" * 64)
            # GPT-family answer is physically presented in slot B; A wins, so
            # the known result is an other-family win.
            repo, second, _, a2, b2 = chain(db, rq="RQ6", repetition=2)
            second.presentation_order = "SELF_B"; second.answer_a_author_id = "claude-v1"; second.answer_b_author_id = "gpt-4"
            run_b = ControlledExecutionService(repo, ControlledEvaluationEngine(DeterministicMockProvider([MockScenario.ANSWER_A]))).execute_single(unit=second, request=request(second, a2, b2), idempotency_key="2" * 64)
            assert run_a.passes[0].presented_answer_a_id == first.answer_a_id
            assert run_b.passes[0].presented_answer_b_id == second.answer_b_id
            evidence = [rq6_from_run(run_a, first), rq6_from_run(run_b, second)]
            assert [item.outcome for item in evidence] == ["SELF", "OTHER"]
            metric = analyze_rq6(evidence, iterations=20)["self_family_preference"]
            assert metric.numerator == 1 and metric.denominator == 2 and metric.value == 0.5
    finally:
        engine.dispose()
