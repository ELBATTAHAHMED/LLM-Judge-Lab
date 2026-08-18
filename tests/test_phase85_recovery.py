"""Deterministic chaos coverage for the controlled pass-attempt ledger.

These tests have no network transport.  Their invocation counters are the
proof that retries never create a new scientific pass or RQ2 repetition.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from controlled_evaluation import ControlledEvaluationEngine, ControlledExecutionService
from controlled_models import PassAttempt
from mock_provider import DeterministicMockProvider, MockScenario
from test_phase5_offline_integration import chain, request


@pytest.fixture()
def session(tmp_path):
    path = tmp_path / "recovery.sqlite"
    cfg = Config(str(ROOT / "alembic.ini")); cfg.set_main_option("script_location", str(ROOT / "alembic")); cfg.set_main_option("sqlalchemy.url", f"sqlite:///{path.as_posix()}")
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    try:
        with sessionmaker(bind=engine)() as db:
            yield db
    finally:
        engine.dispose()


def execute(db, scenarios, *, rq="RQ1", repetition=0):
    repo, unit, _, a, b = chain(db, rq=rq)
    unit.repetition_index = repetition
    mock = DeterministicMockProvider(scenarios)
    run = ControlledExecutionService(repo, ControlledEvaluationEngine(mock)).execute_single(
        unit=unit, request=request(unit, a, b).model_copy(update={"repetition_index": repetition}), idempotency_key=(f"{rq}-{repetition}".encode().hex() * 64)[:64]
    )
    db.commit()
    return run, mock


@pytest.mark.parametrize(("scenarios", "calls", "state"), [
    ([MockScenario.RATE_LIMIT, MockScenario.ANSWER_A], 2, "SUCCEEDED"),
    ([MockScenario.HTTP_5XX, MockScenario.ANSWER_A], 2, "SUCCEEDED"),
    ([MockScenario.CONNECTION, MockScenario.ANSWER_A], 2, "SUCCEEDED"),
    ([MockScenario.TIMEOUT, MockScenario.ANSWER_A], 2, "SUCCEEDED"),
    ([MockScenario.INVALID_JSON], 1, "FAILED_FINAL"),
    ([MockScenario.REFUSAL], 1, "FAILED_FINAL"),
])
def test_retry_matrix_exact_calls(session, scenarios, calls, state):
    run, mock = execute(session, scenarios)
    attempts = list(session.query(PassAttempt).filter_by(run_id=run.id, pass_number=1).order_by(PassAttempt.attempt_index))
    assert mock.calls == calls
    assert attempts[-1].state == state
    assert len(run.passes) == 1


def test_rq2_retries_preserve_scientific_repetition_index(session):
    run, mock = execute(session, [MockScenario.RATE_LIMIT, MockScenario.HTTP_5XX, MockScenario.ANSWER_B], rq="RQ2", repetition=3)
    attempts = list(session.query(PassAttempt).filter_by(run_id=run.id, pass_number=1))
    assert mock.calls == 3 and run.repetition_index == 3
    assert [row.details_json["repetition_index"] for row in attempts] == [3, 3, 3]


def test_successful_pass_is_never_invoked_twice(session):
    run, mock = execute(session, [MockScenario.ANSWER_A])
    # The persisted ledger has exactly one success for this scientific pass.
    successes = session.query(PassAttempt).filter_by(run_id=run.id, pass_number=1, state="SUCCEEDED").count()
    assert mock.calls == 1 and successes == 1


class CrashAfterInProgress:
    calls = 0
    def evaluate(self, _request):
        self.calls += 1
        raise KeyboardInterrupt("simulated process termination after outbound boundary")


def test_ambiguous_attempt_is_never_automatically_resent(session):
    repo, unit, _, a, b = chain(session, rq="RQ1")
    crashing = CrashAfterInProgress()
    service = ControlledExecutionService(repo, ControlledEvaluationEngine(crashing))
    with pytest.raises(KeyboardInterrupt):
        service.execute_single(unit=unit, request=request(unit, a, b), idempotency_key="a" * 64)
    attempt = session.query(PassAttempt).one()
    assert attempt.state == "AMBIGUOUS" and crashing.calls == 1
    # The existing running run is a recovery boundary, not a second request.
    resumed = service.execute_single(unit=unit, request=request(unit, a, b), idempotency_key="a" * 64)
    assert resumed.id and crashing.calls == 1
