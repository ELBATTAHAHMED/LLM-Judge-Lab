from __future__ import annotations

import hashlib
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from controlled_evaluation import (  # noqa: E402
    ControlledEvaluationEngine, ControlledExecutionService, EvaluationRequest,
    derive_dual_pass_decision,
)
from controlled_models import ControlledRun  # noqa: E402
from controlled_persistence import ControlledPersistence, Outcome  # noqa: E402
from controlled_real_execution import BudgetLedger, ExecutionCaps, RealExecutionProfile  # noqa: E402
from mock_provider import DeterministicMockProvider, MockScenario  # noqa: E402
from model_registry import Provider, UnsupportedModelError, get_model_spec  # noqa: E402
from models import Answer, JudgeDecision, Prompt  # noqa: E402


@pytest.fixture()
def isolated_engine(tmp_path):
    db_path = tmp_path / "phase2.sqlite"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    try:
        yield engine
    finally:
        engine.dispose()


def setup_unit(session):
    prompt = Prompt(text="Which answer is better?", category="test")
    session.add(prompt); session.flush()
    a = Answer(prompt_id=prompt.id, model_name="author-a", text="Answer A", word_count=2)
    b = Answer(prompt_id=prompt.id, model_name="author-b", text="Answer B", word_count=2)
    session.add_all([a, b]); session.flush()
    repo = ControlledPersistence(session)
    dataset = repo.get_or_create_dataset_version(source_name="test", version="v1", source_checksum="a" * 64, import_status="SUCCEEDED")
    experiment = repo.create_experiment(dataset_version=dataset, experiment_name="phase2", research_question="RQ", hypothesis="offline")
    condition = repo.create_condition(experiment=experiment, condition_code="BASE", label="base", condition_json={}, protocol_version="p1", prompt_template_version="judge-pairwise-structured-v1")
    manifest = repo.create_manifest(experiment=experiment, rq_code="RQ1", protocol_version="p1", analysis_version="a1", dataset_snapshot_id="s", dataset_checksum="b" * 64, manifest_sha256="c" * 64, manifest_json={})
    unit = repo.register_unit(experiment=experiment, manifest=manifest, condition=condition, prompt_id=prompt.id, answer_a_id=a.id, answer_b_id=b.id, prompt_category="test", judge_model="gpt-4o-mini", provider="OPENAI", provider_model="gpt-4o-mini", prompt_template_version="judge-pairwise-structured-v1", presentation_order="AB", repetition_index=3, randomization_block="block", data_split="test", inclusion_status="INCLUDED")
    return repo, unit, a, b


def request_for(unit, a, b, **changes):
    values = dict(question="Which answer is better?", answer_a="Answer A", answer_b="Answer B", judge_name="gpt-4o-mini", provider=Provider.OPENAI, requested_model="gpt-4o-mini", temperature=0.0, top_p=1.0, seed=123, prompt_template_version="judge-pairwise-structured-v1", experiment_id=unit.experiment_id, controlled_unit_id=unit.id, repetition_index=unit.repetition_index, pass_number=1, original_answer_a_id=a.id, original_answer_b_id=b.id, presented_answer_a_id=a.id, presented_answer_b_id=b.id)
    values.update(changes)
    return EvaluationRequest(**values)


def service(repo, scenarios, **kwargs):
    return ControlledExecutionService(repo, ControlledEvaluationEngine(DeterministicMockProvider(scenarios, **kwargs)))


def test_01_answer_a_normalizes_and_persists(isolated_engine):
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        repo, unit, a, b = setup_unit(session); run = service(repo, [MockScenario.ANSWER_A]).execute_single(unit=unit, request=request_for(unit, a, b), idempotency_key="01" * 32)
        assert (run.final_result_type, run.final_winner_answer_id, run.passes[0].raw_verdict) == ("ANSWER_A", a.id, "ANSWER_A")


def test_02_answer_b_normalizes_and_persists(isolated_engine):
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        repo, unit, a, b = setup_unit(session); run = service(repo, [MockScenario.ANSWER_B]).execute_single(unit=unit, request=request_for(unit, a, b), idempotency_key="02" * 32)
        assert run.final_winner_answer_id == b.id


def test_03_tie_is_a_real_outcome(isolated_engine):
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        repo, unit, a, b = setup_unit(session); run = service(repo, [MockScenario.TIE]).execute_single(unit=unit, request=request_for(unit, a, b), idempotency_key="03" * 32)
        assert (run.final_result_type, run.status, run.final_parse_status) == ("TIE", "SUCCEEDED", "PARSED")


def test_04_unknown_remains_distinct(isolated_engine):
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        repo, unit, a, b = setup_unit(session); run = service(repo, [MockScenario.UNKNOWN]).execute_single(unit=unit, request=request_for(unit, a, b), idempotency_key="04" * 32)
        assert (run.final_result_type, run.final_parse_status) == ("UNKNOWN", "MISSING_RESPONSE")


def test_05_invalid_response_is_not_a_tie(isolated_engine):
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        repo, unit, a, b = setup_unit(session); run = service(repo, [MockScenario.INVALID_JSON]).execute_single(unit=unit, request=request_for(unit, a, b), idempotency_key="05" * 32)
        assert (run.final_result_type, run.final_parse_status, run.status) == ("ERROR", "INVALID", "FAILED")


def test_06_provider_error_is_not_a_vote(isolated_engine):
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        repo, unit, a, b = setup_unit(session); run = service(repo, [MockScenario.PROVIDER_ERROR]).execute_single(unit=unit, request=request_for(unit, a, b), idempotency_key="06" * 32)
        assert (run.final_parse_status, run.error_code) == ("PROVIDER_ERROR", "PROVIDER_ERROR")


def test_07_timeout_is_not_unknown_or_tie(isolated_engine):
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        # Timeout has one retry under the frozen Phase 8.5 policy; both
        # deterministic attempts time out so the terminal classification is
        # still a timeout rather than a fabricated scientific verdict.
        repo, unit, a, b = setup_unit(session); run = service(repo, [MockScenario.TIMEOUT, MockScenario.TIMEOUT]).execute_single(unit=unit, request=request_for(unit, a, b), idempotency_key="07" * 32)
        assert (run.final_parse_status, run.error_code) == ("TIMEOUT", "TIMEOUT")


def test_refusal_remains_a_distinct_persisted_outcome(isolated_engine):
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        repo, unit, a, b = setup_unit(session)
        run = service(repo, [MockScenario.REFUSAL]).execute_single(unit=unit, request=request_for(unit, a, b), idempotency_key="18" * 32)
        assert (run.final_parse_status, run.passes[0].outcome, run.passes[0].parse_status) == ("REFUSAL", "REFUSAL", "REFUSAL")


def test_budget_guard_counts_retries_as_attempts_without_creating_a_new_scientific_pass(isolated_engine):
    """A blocked retry is stopped before its fake evaluator can be called."""
    Session = sessionmaker(bind=isolated_engine)
    profile = RealExecutionProfile(
        execution_mode="REAL", authorization_token="fixture", dataset_version_id="fixture",
        manifest_ids=("fixture",), manifest_hashes=("fixture",), source_commit="fixture", source_tag="fixture",
        pricing_version="pricing-config-v1", routing_version="fixture", routing_fingerprint="fixture",
        prompt_version="fixture", prompt_sha256="fixture", retry_policy_version="fixture", failure_policy_version="fixture",
        analysis_version="fixture", model_ids=("gpt-4o-mini",), configured_upstreams=(),
        caps=ExecutionCaps(1, 1, 100_000, 1_000, Decimal("10")),
    )
    with Session.begin() as session:
        repo, unit, a, b = setup_unit(session)
        req = request_for(unit, a, b)
        ledger = BudgetLedger(profile)
        first = ledger.reserve(run_id="run", request=req)
        assert first["estimated_input_tokens"] > 0 and ledger.snapshot()["scientific_passes"] == 1
        with pytest.raises(PermissionError):
            ledger.reserve(run_id="run", request=req.model_copy(update={"retry_count": 1}))
        fake = DeterministicMockProvider([MockScenario.ANSWER_A])
        run = ControlledExecutionService(repo, ControlledEvaluationEngine(fake), before_provider_attempt=lambda *_: (_ for _ in ()).throw(PermissionError("cap"))).execute_single(unit=unit, request=req, idempotency_key="19" * 32)
        assert fake.calls == 0 and run.error_code == "BUDGET_EXCEEDED" and run.passes[0].outcome == "API_ERROR"


def test_08_requested_and_effective_model_are_both_preserved(isolated_engine):
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        repo, unit, a, b = setup_unit(session); run = service(repo, [MockScenario.ANSWER_A], effective_model="gpt-4o-mini-2026-08-06").execute_single(unit=unit, request=request_for(unit, a, b), idempotency_key="08" * 32)
        assert (run.requested_model, run.effective_model) == ("gpt-4o-mini", "gpt-4o-mini-2026-08-06")


def test_09_provider_identity_is_preserved(isolated_engine):
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        repo, unit, a, b = setup_unit(session); run = service(repo, [MockScenario.ANSWER_A]).execute_single(unit=unit, request=request_for(unit, a, b), idempotency_key="09" * 32)
        assert (run.provider, run.provider_model) == ("OPENAI", "NOT_RETURNED")


def test_10_single_pass_creates_one_run_and_one_pass(isolated_engine):
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        repo, unit, a, b = setup_unit(session); run = service(repo, [MockScenario.ANSWER_A]).execute_single(unit=unit, request=request_for(unit, a, b), idempotency_key="10" * 32)
        assert (run.run_kind, len(run.passes)) == ("STANDARD", 1)


def test_11_dual_pass_persists_two_independent_passes(isolated_engine):
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        repo, unit, a, b = setup_unit(session); run = service(repo, [MockScenario.ANSWER_A, MockScenario.ANSWER_B]).execute_dual(unit=unit, first_request=request_for(unit, a, b), idempotency_key="11" * 32)
        assert (run.run_kind, len(run.passes), [p.pass_number for p in run.passes]) == ("CALIBRATED_DUAL_PASS", 2, [1, 2])


def test_12_swap_mapping_maps_presented_slots_to_original_answers(isolated_engine):
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        repo, unit, a, b = setup_unit(session); run = service(repo, [MockScenario.ANSWER_A, MockScenario.ANSWER_A]).execute_dual(unit=unit, first_request=request_for(unit, a, b), idempotency_key="12" * 32)
        assert [p.winner_answer_id for p in run.passes] == [a.id, b.id]


def test_13_consistent_dual_pass_selects_original_a(isolated_engine):
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        repo, unit, a, b = setup_unit(session); run = service(repo, [MockScenario.ANSWER_A, MockScenario.ANSWER_B]).execute_dual(unit=unit, first_request=request_for(unit, a, b), idempotency_key="13" * 32)
        assert (run.dual_pass_classification, run.metadata_json["derived_dual_pass_decision"], run.final_result_type, run.final_winner_answer_id) == ("SAME_DECISIVE_WINNER", "CONSISTENT", "ANSWER_A", a.id)


def test_14_conflicting_dual_pass_is_disagreement_not_position_bias(isolated_engine):
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        repo, unit, a, b = setup_unit(session); run = service(repo, [MockScenario.ANSWER_A, MockScenario.ANSWER_A]).execute_dual(unit=unit, first_request=request_for(unit, a, b), idempotency_key="14" * 32)
        assert (run.dual_pass_classification, run.metadata_json["derived_dual_pass_decision"], run.final_result_type, run.status) == ("DECISIVE_FLIP", "DISAGREEMENT", "PARTIAL", "PARTIAL")


def test_15_retry_count_is_not_repetition_index(isolated_engine):
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        repo, unit, a, b = setup_unit(session); run = service(repo, [MockScenario.ANSWER_A]).execute_single(unit=unit, request=request_for(unit, a, b, retry_count=2), idempotency_key="15" * 32)
        assert (run.retry_count, run.repetition_index) == (2, 3)


def test_16_live_sandbox_is_not_returned_by_controlled_query(isolated_engine):
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        repo, unit, a, b = setup_unit(session)
        session.add(JudgeDecision(prompt_id=unit.prompt_id, judge_model_name="live", answer_a_id=a.id, answer_b_id=b.id, position_a_id=a.id, winner_id=a.id, reasoning="sandbox")); session.flush()
        service(repo, [MockScenario.ANSWER_A]).execute_single(unit=unit, request=request_for(unit, a, b), idempotency_key="16" * 32)
        assert len(repo.controlled_runs()) == 1


def test_17_legacy_judge_decisions_are_untouched(isolated_engine):
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        repo, unit, a, b = setup_unit(session); before = session.query(JudgeDecision).count()
        service(repo, [MockScenario.ANSWER_A]).execute_single(unit=unit, request=request_for(unit, a, b), idempotency_key="17" * 32)
        assert session.query(JudgeDecision).count() == before


def test_registry_and_input_validation_fail_before_mock_execution(isolated_engine):
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        _, unit, a, b = setup_unit(session)
        with pytest.raises(UnsupportedModelError): get_model_spec("llama3")
        with pytest.raises(ValidationError): request_for(unit, a, b, question="", seed="not-an-int")
        with pytest.raises(ValidationError): request_for(unit, a, b, judge_name="deepseek/deepseek-chat", provider=Provider.OPENROUTER, requested_model="deepseek/deepseek-chat", seed=1)


def test_18_ensemble_failures_are_not_scientific_votes(monkeypatch):
    from judge_engine import JudgeResult, call_multi_judge_ensemble

    def fake_call_judge(*, model_name, **_):
        if model_name == "broken":
            raise RuntimeError("offline fake failure")
        return JudgeResult("A", "offline", model_name, 1, 1)

    monkeypatch.setattr("judge_engine.call_judge", fake_call_judge)
    result = call_multi_judge_ensemble("q", "a", "b", ["working", "broken"], mitigation_strategy="none")
    assert result.consensus_verdict == "A"
    assert result.vote_counts == {"A": 1, "B": 0, "TIE": 0, "UNKNOWN": 0, "FAILED": 1}
