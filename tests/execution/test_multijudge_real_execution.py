"""Provider-free tests for the durable frozen multi-judge execution runner."""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from multijudge_execution_models import MultiJudgeExecutionAttempt, MultiJudgeExecutionSlot  # noqa: E402
from multijudge_real_execution import (  # noqa: E402
    HARD_CAP_USD, MultiJudgePreflightError,
    MultiJudgeRealRunner, _map_vote, _validate_routes_and_pricing, credential_presence,
)
from controlled_persistence import Outcome  # noqa: E402


class FakeTransport:
    def __init__(self, outcomes=None):
        self.outcomes = list(outcomes or ["OK"])
        self.calls = 0

    def __call__(self, endpoint, headers, payload):
        self.calls += 1
        outcome = self.outcomes.pop(0) if self.outcomes else "OK"
        if outcome == "TIMEOUT":
            raise TimeoutError("fixture timeout")
        provider = {
            "anthropic/claude-3-haiku": "amazon-bedrock",
            "deepseek/deepseek-chat": "streamlake",
            "meta-llama/llama-3.3-70b-instruct": "deepinfra/turbo",
        }.get(payload["model"])
        response = {
            "id": f"fixture-{self.calls}", "model": payload["model"],
            "usage": {"prompt_tokens": 12, "completion_tokens": 7},
            "choices": [{"message": {"content": '{"verdict":"ANSWER_A","criteria_scores":{"correctness":5,"relevance":5,"completeness":5,"clarity":5,"safety":5},"confidence":0.9,"explanation":"fixture"}'}}],
        }
        if provider:
            response["openrouter_metadata"] = {"provider": provider}
        return response


@pytest.fixture()
def session_factory(tmp_path):
    path = tmp_path / "multijudge.sqlite"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{path.as_posix()}")
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    factory = sessionmaker(bind=engine)
    try:
        yield factory
    finally:
        engine.dispose()


@pytest.fixture()
def configured_credentials(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-openai")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fixture-openrouter")


def test_full_materialization_is_idempotent_and_preflight_never_calls_transport(session_factory, configured_credentials):
    fake = FakeTransport(); runner = MultiJudgeRealRunner(transport=fake)
    with session_factory() as session:
        first = runner.preflight(session); session.commit()
    with session_factory() as session:
        second = runner.preflight(session); session.commit()
        batch = runner.store.batch_for_manifest(session, runner.frozen.manifest_sha256)
        slots = list(session.query(MultiJudgeExecutionSlot).filter_by(batch_id=batch.id))
    assert first["state"] == second["state"] == "READY"
    assert first["materialized_pairs"] == 1611 and first["materialized_planned_passes"] == 6444
    assert len(slots) == len({slot.idempotency_key for slot in slots}) == 6444
    assert fake.calls == 0


def test_durable_resume_retry_and_completed_skip(session_factory, configured_credentials):
    fake = FakeTransport(["TIMEOUT", "OK", "OK"]); runner = MultiJudgeRealRunner(transport=fake)
    with session_factory() as session:
        runner.preflight(session); session.commit()
    first = runner.execute(session_factory, confirm_paid_run="I_CONFIRM_MULTI_JUDGE_PAID_EXECUTION", max_slots=1)
    assert first["completed_scientific_slots"] == 0 and first["attempts"] == 1 and first["pending"] == 6444
    second = runner.execute(session_factory, confirm_paid_run="I_CONFIRM_MULTI_JUDGE_PAID_EXECUTION", max_slots=1)
    assert second["completed_scientific_slots"] == 1 and second["attempts"] == 2
    third = runner.execute(session_factory, confirm_paid_run="I_CONFIRM_MULTI_JUDGE_PAID_EXECUTION", max_slots=1)
    assert third["completed_scientific_slots"] == 2 and fake.calls == 3
    with session_factory() as session:
        attempts = list(session.query(MultiJudgeExecutionAttempt).order_by(MultiJudgeExecutionAttempt.attempt_index))
        assert attempts[0].state == "FAILED_RETRYABLE" and attempts[1].state == "SUCCEEDED"
        assert len({row.attempt_id for row in attempts}) == len(attempts)


def test_restart_marks_sent_request_ambiguous_and_budget_stops_before_transport(session_factory, configured_credentials):
    runner = MultiJudgeRealRunner(transport=FakeTransport())
    with session_factory() as session:
        runner.preflight(session)
        batch = runner.store.batch_for_manifest(session, runner.frozen.manifest_sha256)
        slot = session.query(MultiJudgeExecutionSlot).filter_by(batch_id=batch.id, status="PENDING").first()
        slot_id = slot.id
        assert runner.store.reserve_and_mark_sent(session, batch, slot.id, Decimal("0.0001")) is not None
        session.commit()
    with session_factory() as session:
        batch = runner.store.batch_for_manifest(session, runner.frozen.manifest_sha256)
        runner.store.recover_after_restart(session, batch); session.commit()
        assert session.get(MultiJudgeExecutionSlot, slot_id).status == "AMBIGUOUS"
        pending = session.query(MultiJudgeExecutionSlot).filter_by(batch_id=batch.id, status="PENDING").first()
        assert runner.store.reserve_and_mark_sent(session, batch, pending.id, HARD_CAP_USD) is None
        assert session.get(MultiJudgeExecutionSlot, pending.id).status == "BUDGET_STOPPED"


def test_credentials_route_and_human_reference_safety_fail_closed(session_factory, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False); monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert credential_presence() == {"openai": False, "openrouter": False}
    runner = MultiJudgeRealRunner(transport=FakeTransport())
    with session_factory() as session:
        report = runner.preflight(session); session.commit()
    assert report["state"] == "NOT READY"
    with pytest.raises(MultiJudgePreflightError, match="credentials"):
        runner.execute(session_factory, confirm_paid_run="I_CONFIRM_MULTI_JUDGE_PAID_EXECUTION")
    runner.frozen.manifest["scientific_configuration"]["judges"][0]["route"] = "wrong-route"
    with pytest.raises(MultiJudgePreflightError, match="route"):
        _validate_routes_and_pricing(runner.frozen)
    import multijudge_real_execution
    original = multijudge_real_execution._copy_rows
    def reject_human_preferences(table):
        if table == "human_preferences":
            raise AssertionError("human reference access is prohibited")
        return original(table)
    monkeypatch.setattr(multijudge_real_execution, "_copy_rows", reject_human_preferences)
    prompts, answers = runner._payload_source()
    assert prompts and answers


def test_default_cli_invocation_is_preflight_only(session_factory, configured_credentials, monkeypatch):
    import run_multijudge_consensus as cli
    fake = FakeTransport(); runner = MultiJudgeRealRunner(transport=fake)
    monkeypatch.setattr(cli, "SessionLocal", session_factory)
    monkeypatch.setattr(cli, "MultiJudgeRealRunner", lambda: runner)
    assert cli.main([]) == 0
    assert fake.calls == 0


@pytest.mark.parametrize("presentation,outcome,expected", [
    ("AB", Outcome.ANSWER_A, "ORIGINAL_ANSWER_1"),
    ("AB", Outcome.ANSWER_B, "ORIGINAL_ANSWER_2"),
    ("AB", Outcome.TIE, "TIE"),
    ("BA", Outcome.ANSWER_A, "ORIGINAL_ANSWER_2"),
    ("BA", Outcome.ANSWER_B, "ORIGINAL_ANSWER_1"),
    ("BA", Outcome.TIE, "TIE"),
])
def test_all_valid_frozen_display_mappings_round_trip(presentation, outcome, expected):
    slot = SimpleNamespace(
        presentation=presentation, original_answer_1_id=1318, original_answer_2_id=1635,
        displayed_a_answer_id=1318 if presentation == "AB" else 1635,
        displayed_b_answer_id=1635 if presentation == "AB" else 1318,
    )
    assert _map_vote(slot, outcome) == expected


def test_unknown_is_a_non_vote_and_invalid_or_provider_error_never_map(session_factory, configured_credentials):
    ba_slot = SimpleNamespace(original_answer_1_id=1318, original_answer_2_id=1635, displayed_a_answer_id=1635, displayed_b_answer_id=1318)
    # This is the exact former failure: valid parsed UNKNOWN reached _map_vote.
    assert _map_vote(ba_slot, Outcome.UNKNOWN) is None
    runner = MultiJudgeRealRunner(transport=FakeTransport())
    with session_factory() as session:
        runner.preflight(session)
        batch = runner.store.batch_for_manifest(session, runner.frozen.manifest_sha256)
        slots = list(session.query(MultiJudgeExecutionSlot).filter_by(batch_id=batch.id, status="PENDING").limit(2))
        for slot, outcome, error in ((slots[0], Outcome.INVALID_RESPONSE, "INVALID_RESPONSE"), (slots[1], Outcome.API_ERROR, "PROVIDER_ERROR")):
            attempt = runner.store.reserve_and_mark_sent(session, batch, slot.id, Decimal("0.0001"))
            result = SimpleNamespace(outcome=outcome, provider_reported_cost=None, input_tokens=None, output_tokens=None, provider_response_id=None, effective_model="NOT_RETURNED", route_provenance=None, parse_status="INVALID", model_version=None, latency_ms=0, criterion_scores=None, explanation=None, error_code=error)
            assert runner.store.persist_result(session, slot.id, attempt.attempt_id, result) == "FAILED_FINAL"
            assert slot.mapped_vote is None
        session.commit()


def test_ambiguous_slot_is_never_replayed_while_other_pending_slots_resume(session_factory, configured_credentials):
    fake = FakeTransport(); runner = MultiJudgeRealRunner(transport=fake)
    with session_factory() as session:
        runner.preflight(session)
        batch = runner.store.batch_for_manifest(session, runner.frozen.manifest_sha256)
        protected = session.query(MultiJudgeExecutionSlot).filter_by(batch_id=batch.id, status="PENDING").first()
        protected_id = protected.id
        runner.store.reserve_and_mark_sent(session, batch, protected_id, Decimal("0.0001"))
        runner.store.recover_after_restart(session, batch); session.commit()
    report = runner.execute(session_factory, confirm_paid_run="I_CONFIRM_MULTI_JUDGE_PAID_EXECUTION", max_slots=1)
    with session_factory() as session:
        protected = session.get(MultiJudgeExecutionSlot, protected_id)
        protected_attempts = session.query(MultiJudgeExecutionAttempt).filter_by(slot_id=protected_id).count()
    assert protected.status == "AMBIGUOUS" and protected_attempts == 1
    assert report["ambiguous"] == 1 and report["completed_scientific_slots"] == 1 and fake.calls == 1
