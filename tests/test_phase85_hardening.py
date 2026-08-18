from __future__ import annotations

from decimal import Decimal
import sys
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from controlled_evaluation import ControlledEvaluationEngine, ControlledExecutionService
from controlled_freeze import FrozenPair, canonical_dataset_checksum, freeze_reference_pairs
from controlled_models import Experiment
from controlled_prompt import PROMPT_TEMPLATE_VERSION, build_messages, prompt_hash
from controlled_providers import ProviderExecutionGate, adapter_for_judge
from controlled_persistence import Outcome
from phase4_metrics import RQ1Unit, analyze_rq1
from mock_provider import DeterministicMockProvider, MockScenario
from test_phase5_offline_integration import chain, request


@pytest.fixture()
def isolated_engine(tmp_path):
    path = tmp_path / "phase85.sqlite"
    cfg = Config(str(ROOT / "alembic.ini")); cfg.set_main_option("script_location", str(ROOT / "alembic")); cfg.set_main_option("sqlalchemy.url", f"sqlite:///{path.as_posix()}")
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    try:
        yield engine
    finally:
        engine.dispose()


def test_schema_accepts_long_presentation_orders_and_direct_run_unit_fk(isolated_engine):
    columns = {column["name"]: column for column in inspect(isolated_engine).get_columns("experimental_units")}
    assert columns["presentation_order"]["type"].length >= len("SELF_A")
    assert "experimental_unit_id" in {column["name"] for column in inspect(isolated_engine).get_columns("runs")}
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        repo, unit, _, a, b = chain(session, rq="RQ3")
        unit.presentation_order = "AB_BA"
        run = ControlledExecutionService(repo, ControlledEvaluationEngine(DeterministicMockProvider([MockScenario.ANSWER_A]))).execute_single(unit=unit, request=request(unit, a, b), idempotency_key="8" * 64)
        assert run.experimental_unit_id == unit.id


def test_frozen_prompt_is_neutral_and_version_fingerprinted():
    messages = build_messages(question="Q", answer_a="A", answer_b="B")
    assert PROMPT_TEMPLATE_VERSION == "controlled-judge-pairwise-v1" and len(prompt_hash()) == 64
    assert "original" not in messages[1]["content"].lower() and "variant" not in messages[1]["content"].lower()
    assert "Answer A" in messages[1]["content"] and "Answer B" in messages[1]["content"]


def test_reversed_pair_policy_is_deterministic_and_excludes_conflicts():
    first = FrozenPair(1, 1, 10, 20, "a", "b", "gpt-4", "claude-v1", "x", "ANSWER_A")
    reverse_same = FrozenPair(2, 1, 20, 10, "b", "a", "claude-v1", "gpt-4", "x", "ANSWER_B")
    conflicting = FrozenPair(3, 2, 30, 40, "c", "d", "gpt-4", "claude-v1", "x", "ANSWER_A")
    reverse_conflict = FrozenPair(4, 2, 40, 30, "d", "c", "claude-v1", "gpt-4", "x", "ANSWER_A")
    frozen, report = freeze_reference_pairs([first, reverse_same, conflicting, reverse_conflict])
    assert len(frozen) == 1 and frozen[0].human_label == "ANSWER_A"
    assert report["collapsed_rows"] == 1 and report["conflicting_unordered_groups_excluded"] == 1
    assert canonical_dataset_checksum(frozen) == canonical_dataset_checksum(frozen)


def test_real_adapter_is_locked_and_fixture_normalizes_markdown_json(isolated_engine):
    gate = ProviderExecutionGate(mode="REAL", authorization_token="test-only", verified_pricing_version="fixture", max_provider_calls=1, max_input_tokens=1, max_output_tokens=1, max_usd=1)
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        _, unit, _, a, b = chain(session)
        req = request(unit, a, b).model_copy(update={"prompt_template_version": PROMPT_TEMPLATE_VERSION})
        locked = adapter_for_judge("gpt-4o-mini")
        with pytest.raises(PermissionError): locked.evaluate(req)
        adapter = adapter_for_judge("gpt-4o-mini", gate=gate, transport=lambda *_: {"id": "chatcmpl-fixture", "model": "gpt-4o-mini", "choices": [{"message": {"content": "```json\n{\"verdict\":\"ANSWER_A\",\"criteria_scores\":{\"correctness\":5,\"relevance\":5,\"completeness\":5,\"clarity\":5,\"safety\":5},\"confidence\":0.9,\"explanation\":\"fixture\"}\n```"}}]})
        result = ControlledEvaluationEngine(adapter).evaluate(req)
        assert result.outcome is Outcome.ANSWER_A and result.provider_response_id == "chatcmpl-fixture" and result.effective_model == "gpt-4o-mini"


def test_variant_text_round_trip_without_legacy_answer_insert_and_kappa_ci(isolated_engine):
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        repo, unit, _, a, _ = chain(session, rq="RQ4")
        variant = repo.get_or_create_variant(experiment=session.get(Experiment, unit.experiment_id), original_answer_id=a.id, condition_code="VERBOSITY_REDUNDANCY", transformation_method="EXACT_DUPLICATION", transformation_version="phase3-controlled-v1", original_checksum="a" * 64, variant_checksum="b" * 64, variant_text="A response\n\nA response", original_word_count=2, variant_word_count=4, validation_status="VALID", validation_details={})
        unit.counterfactual_variant_id = variant.id
        assert variant.variant_answer_id is None and variant.variant_text.endswith("A response") and unit.counterfactual_variant_id == variant.id
    rows = [RQ1Unit("CONTROLLED", str(index), "RQ1", "judge-a", "BASE", human, judge, "c") for index, (human, judge) in enumerate((("ANSWER_A", "ANSWER_A"), ("ANSWER_A", "ANSWER_B"), ("ANSWER_B", "ANSWER_B"), ("TIE", "TIE")), 1)]
    result = analyze_rq1(rows, seed=8, iterations=100)
    assert result["cohens_kappa"].ci_low is not None and "judge:judge-a:exact_agreement" in result and "category:c:exact_agreement" in result
