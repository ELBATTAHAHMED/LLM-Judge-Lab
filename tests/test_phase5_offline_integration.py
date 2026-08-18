from __future__ import annotations

import hashlib
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from controlled_analysis_adapter import pass_outcome, resume_state, rq1_from_run, rq2_from_run, rq3_from_run  # noqa: E402
from controlled_evaluation import ControlledEvaluationEngine, ControlledExecutionService, EvaluationRequest  # noqa: E402
from controlled_models import CounterfactualVariant, ControlledRun, ExperimentalUnit  # noqa: E402
from controlled_persistence import ControlledPersistence  # noqa: E402
from mock_provider import DeterministicMockProvider, MockScenario  # noqa: E402
from model_registry import Provider  # noqa: E402
from models import Answer, Prompt  # noqa: E402
from phase3_planning import PairRecord, call_plan, generate_units, manifest  # noqa: E402
from phase3_transforms import make_format_variant, make_verbosity_variant, validate_format_variant, validate_verbosity_variant  # noqa: E402
from phase4_metrics import RQ2Repetition, RQ6Unit, RQ7Pair, VariantPair, analyze_rq1, analyze_rq2, analyze_rq3, analyze_rq4, analyze_rq5, analyze_rq6, analyze_rq7  # noqa: E402


@pytest.fixture()
def isolated_engine(tmp_path):
    path = tmp_path / "phase5.sqlite"; cfg = Config(str(ROOT / "alembic.ini")); cfg.set_main_option("script_location", str(ROOT / "alembic")); cfg.set_main_option("sqlalchemy.url", f"sqlite:///{path.as_posix()}")
    command.upgrade(cfg, "0007_pass_attempt_ledger")
    engine = create_engine(f"sqlite:///{path.as_posix()}"); event.listen(engine, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))
    try: yield engine
    finally: engine.dispose()


def chain(session, *, rq="RQ1", human="ANSWER_A", repetition=0, condition="BASELINE", prompt=None, answers=None):
    repo = ControlledPersistence(session)
    if prompt is None:
        prompt = Prompt(text="Which answer is better?", category="synthetic"); session.add(prompt); session.flush()
        answers = (Answer(prompt_id=prompt.id, model_name="gpt-4", text="A response", word_count=2), Answer(prompt_id=prompt.id, model_name="claude-v1", text="B response", word_count=2)); session.add_all(answers); session.flush()
    a, b = answers
    ds = repo.get_or_create_dataset_version(source_name="phase5", version="v1", source_checksum="a" * 64, import_status="SUCCEEDED")
    exp = repo.create_experiment(dataset_version=ds, experiment_name=f"phase5-{rq}-{repetition}-{a.id}", research_question=rq, hypothesis="synthetic")
    cond = repo.create_condition(experiment=exp, condition_code=condition, label=condition, condition_json={}, protocol_version="phase5", prompt_template_version="judge-pairwise-structured-v1")
    man = repo.create_manifest(experiment=exp, rq_code=rq, protocol_version="phase5", analysis_version="phase4-analysis-v1", dataset_snapshot_id="synthetic", dataset_checksum="b" * 64, manifest_sha256=hashlib.sha256(f"{rq}-{a.id}-{repetition}".encode()).hexdigest(), manifest_json={"provider_execution": "mock-only"})
    unit = repo.register_unit(experiment=exp, manifest=man, condition=cond, prompt_id=prompt.id, answer_a_id=a.id, answer_b_id=b.id, prompt_category=prompt.category, judge_model="gpt-4o-mini", provider="OPENAI", provider_model="gpt-4o-mini", prompt_template_version="judge-pairwise-structured-v1", presentation_order="AB", repetition_index=repetition, randomization_block="b", data_split="synthetic", inclusion_status="INCLUDED", temperature=Decimal("0.0"), top_p=Decimal("1.0"), seed=42, human_label=human)
    return repo, unit, prompt, a, b


def request(unit, a, b, *, retry=0):
    return EvaluationRequest(question="Which answer is better?", answer_a=a.text, answer_b=b.text, judge_name="gpt-4o-mini", provider=Provider.OPENAI, requested_model="gpt-4o-mini", temperature=0.0, top_p=1.0, seed=42, prompt_template_version="judge-pairwise-structured-v1", experiment_id=unit.experiment_id, controlled_unit_id=unit.id, repetition_index=unit.repetition_index, pass_number=1, original_answer_a_id=a.id, original_answer_b_id=b.id, presented_answer_a_id=a.id, presented_answer_b_id=b.id, retry_count=retry)


def service(repo, scenarios, **kwargs): return ControlledExecutionService(repo, ControlledEvaluationEngine(DeterministicMockProvider(scenarios, **kwargs)))


def test_full_provenance_dual_pass_roundtrip_and_rq3_metric(isolated_engine):
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        repo, unit, _, a, b = chain(session, rq="RQ3", condition="POSITION_SWAP")
        run = service(repo, [MockScenario.ANSWER_A, MockScenario.ANSWER_A], effective_model="returned-gpt-version").execute_dual(unit=unit, first_request=request(unit, a, b), idempotency_key="1" * 64)
        run_id, unit_id, manifest_id = run.id, unit.id, unit.manifest_id
    with Session() as session:
        run = session.get(ControlledRun, run_id); unit = session.get(ExperimentalUnit, unit_id)
        assert run and unit and run.metadata_json["manifest_id"] == str(manifest_id)
        assert (run.provider, run.requested_model, run.effective_model, run.prompt_template_version, run.repetition_index, len(run.passes)) == ("OPENAI", "gpt-4o-mini", "returned-gpt-version", "judge-pairwise-structured-v1", 0, 2)
        assert [p.winner_answer_id for p in sorted(run.passes, key=lambda p: p.pass_number)] == [unit.answer_a_id, unit.answer_b_id]
        metric = analyze_rq3([rq3_from_run(run, unit)], seed=3, iterations=50)["paired_decisive_flip_rate"]
        assert metric.value == 1.0 and metric.numerator == metric.denominator == 1


def test_all_outcomes_persist_distinctly_and_rq1_pipeline_excludes_failures(isolated_engine):
    Session = sessionmaker(bind=isolated_engine); rows = []
    scenarios = [MockScenario.ANSWER_A, MockScenario.ANSWER_B, MockScenario.TIE, MockScenario.UNKNOWN, MockScenario.INVALID_JSON, MockScenario.PROVIDER_ERROR, MockScenario.TIMEOUT]
    expected = [("ANSWER_A", "PARSED", "SUCCEEDED"), ("ANSWER_B", "PARSED", "SUCCEEDED"), ("TIE", "PARSED", "SUCCEEDED"), ("UNKNOWN", "MISSING_RESPONSE", "SUCCEEDED"), ("INVALID_RESPONSE", "INVALID", "FAILED"), ("API_ERROR", "PROVIDER_ERROR", "FAILED"), ("TIMEOUT", "TIMEOUT", "FAILED")]
    with Session.begin() as session:
        for idx, scenario in enumerate(scenarios):
            repo, unit, _, a, b = chain(session, human=("ANSWER_A", "ANSWER_B", "TIE", "ANSWER_A", "ANSWER_A", "ANSWER_A", "ANSWER_A")[idx], repetition=idx)
            # The frozen timeout policy performs one transport retry; preserve
            # a timeout terminal state by supplying the retry outcome too.
            sequence = [scenario, MockScenario.TIMEOUT] if scenario is MockScenario.TIMEOUT else [scenario]
            run = service(repo, sequence).execute_single(unit=unit, request=request(unit, a, b), idempotency_key=f"{idx+2:064x}")
            outcome = pass_outcome(run.passes[0]); rows.append(rq1_from_run(run, unit))
            assert (outcome, run.final_parse_status, run.status) == expected[idx]
            assert (run.final_winner_answer_id is None) == (outcome not in {"ANSWER_A", "ANSWER_B"})
    result = analyze_rq1(rows, seed=2, iterations=50)["exact_agreement"]
    assert (result.numerator, result.denominator, result.value, result.invalid_count, result.failure_count, result.unknown_count) == (3, 3, 1.0, 1, 2, 1)


def test_rq2_pair_config_temperature_retry_and_group_bootstrap_integration(isolated_engine):
    Session = sessionmaker(bind=isolated_engine); records = []
    with Session.begin() as session:
        for pair_number, (a_id, b_id) in enumerate(((1, 2), (3, 4))):
            for rep in range(5):
                records.append(RQ2Repetition("CONTROLLED", f"{pair_number}-{rep}", "RQ2", "gpt-4o-mini", "TEMP_0", f"pair-{pair_number}-t0", a_id, b_id, 0.0, rep, 3, "ANSWER_A" if pair_number == 0 or rep < 4 else "ANSWER_B", "OPENAI", "gpt-4o-mini", "judge-pairwise-structured-v1", 1.0, "seeded"))
        records.extend(RQ2Repetition("CONTROLLED", f"temp-{i}", "RQ2", "gpt-4o-mini", "TEMP_07", "pair-0-t07", 1, 2, .7, i, 0, "ANSWER_A", "OPENAI", "gpt-4o-mini", "judge-pairwise-structured-v1", 1.0, "seeded") for i in range(5))
    result = analyze_rq2(records, seed=4, iterations=50)["consistency"]
    assert result.denominator == 3 and result.value == pytest.approx((1 + .8 + 1) / 3)


def test_variant_source_family_mitigation_and_not_estimable_contracts(isolated_engine):
    original = "Only this claim."; verbose = make_verbosity_variant(original); formatted = make_format_variant(original)
    assert validate_verbosity_variant(1, original, verbose).valid and not validate_verbosity_variant(1, original, verbose + " New fact.").valid
    assert validate_format_variant(1, original, formatted).valid and not validate_format_variant(1, original, formatted + "\n- New fact.").valid
    rq4 = analyze_rq4([VariantPair("CONTROLLED", "v", "RQ4", "g", "c", True, "VARIANT", "AB_BA"), VariantPair("CONTROLLED", "bad", "RQ4", "g", "c", False, "VARIANT", "AB_BA")], seed=1, iterations=50)
    rq5 = analyze_rq5([VariantPair("CONTROLLED", "f", "RQ5", "g", "c", True, "ORIGINAL", "AB_BA")], seed=1, iterations=50)
    assert rq4["variant_win_rate"].denominator == 1 and rq4["rejected_variant_count"].numerator == 1 and rq5["original_win_rate"].value == 1
    from phase4_metrics import RQ6Unit
    rq6 = analyze_rq6([RQ6Unit("CONTROLLED", "a", "RQ6", "g", "c", True, "SELF", "A"), RQ6Unit("CONTROLLED", "b", "RQ6", "g", "c", True, "OTHER", "B"), RQ6Unit("CONTROLLED", "m", "RQ6", "g", "c", False, None, None)], iterations=50)["self_family_preference"]
    assert rq6.value == .5 and rq6.denominator == 2
    outcomes = analyze_rq7([RQ7Pair("CONTROLLED", "p", "RQ7", "g", "BASELINE", "p", {"agreement": .8, "position": .6}, {"agreement": .6, "position": .2}), RQ7Pair("CONTROLLED", "q", "RQ7", "g", "BASELINE", "q", {"agreement": .8, "position": .6}, {"agreement": 1.0, "position": .2})])
    assert outcomes["agreement"].value == 0.0 and outcomes["position"].value == pytest.approx(-.4)
    assert analyze_rq4([])["variant_win_rate"].status == "NO_DATA" and analyze_rq7([])["delta"].status == "NOT_ESTIMABLE"


def test_manifest_count_idempotency_resume_and_static_contracts(isolated_engine):
    pairs = [PairRecord(i, 1, i * 2, i * 2 + 1, "A", "B", "gpt-4", "claude-v1", "c", "ANSWER_A") for i in range(1, 4)]
    first, second = generate_units(pairs, "RQ7", limit=3, snapshot_id="fixed"), generate_units(pairs, "RQ7", limit=3, snapshot_id="fixed")
    assert first == second and manifest("RQ7", first, "fixed")["manifest_sha256"] == manifest("RQ7", second, "fixed")["manifest_sha256"]
    assert call_plan(pairs, limit=3, snapshot_id="fixed")["RQ7"]["planned_calls"] == 3 * 4 * 3
    material_change = generate_units(pairs, "RQ7", limit=3, snapshot_id="changed")
    assert manifest("RQ7", first, "fixed")["manifest_sha256"] != manifest("RQ7", material_change, "changed")["manifest_sha256"]
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        repo, unit, _, a, b = chain(session); runner = service(repo, [MockScenario.ANSWER_A]); one = runner.execute_single(unit=unit, request=request(unit, a, b, retry=3), idempotency_key="f" * 64); two = runner.execute_single(unit=unit, request=request(unit, a, b, retry=3), idempotency_key="f" * 64)
        assert one.id == two.id and (one.retry_count, one.repetition_index) == (3, 0)
        state = resume_state([one, SimpleNamespace(idempotency_key="timeout", status="FAILED", error_code="TIMEOUT"), SimpleNamespace(idempotency_key="invalid", status="FAILED", error_code="INVALID_RESPONSE"), SimpleNamespace(idempotency_key="pending", status="PENDING", error_code=None)])
        assert state.completed == ("f" * 64,) and state.retryable == ("timeout",) and state.non_retryable == ("invalid",) and state.pending == ("pending",)
    source = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    assert "phase4_metrics" not in source  # later frontend synchronization remains explicit, not silently mixed.


def test_variant_persistence_and_frozen_full_plan_call_arithmetic(isolated_engine):
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        _, unit, _, a, _ = chain(session, rq="RQ4", condition="VERBOSITY_REDUNDANCY")
        variant_text = make_verbosity_variant(a.text)
        variant_answer = Answer(prompt_id=a.prompt_id, model_name="controlled-variant", text=variant_text, word_count=len(variant_text.split())); session.add(variant_answer); session.flush()
        validation = validate_verbosity_variant(a.id, a.text, variant_text)
        row = CounterfactualVariant(original_answer_id=a.id, variant_answer_id=variant_answer.id, condition_code="VERBOSITY_REDUNDANCY", transformation_method="EXACT_DUPLICATION", transformation_version="phase3-v1", original_checksum=validation.source_checksum, variant_checksum=validation.variant_checksum, original_word_count=validation.source_word_count, variant_word_count=validation.variant_word_count, original_token_estimate=validation.source_word_count, variant_token_estimate=validation.variant_word_count, validation_status=validation.status, validation_details={"source_answer_id": a.id, "valid": validation.valid})
        session.add(row); session.flush(); row_id = row.id
    with Session() as session:
        row = session.get(CounterfactualVariant, row_id)
        assert row and row.original_answer_id != row.variant_answer_id and row.original_checksum != row.variant_checksum and row.validation_status == "VALID"
    pairs = [PairRecord(i, i, i * 2, i * 2 + 1, "A", "B", ("gpt-4", "claude-v1", "llama-13b")[i % 3], ("claude-v1", "llama-13b", "gpt-4")[i % 3], "c", "ANSWER_A") for i in range(1, 601)]
    plan = call_plan(pairs, limit=200, snapshot_id="frozen-16600")
    assert sum(item["planned_calls"] for item in plan.values()) == 16_600
