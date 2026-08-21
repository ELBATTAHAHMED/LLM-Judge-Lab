"""Provider-free tests for the narrow counterbalanced RQ6 execution boundary."""
from __future__ import annotations

import copy
import sys
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from controlled_evaluation import EvaluationRequest
from controlled_real_execution import BudgetLedger, ExecutionCaps, RealExecutionProfile
from model_registry import Provider
from rq6_counterbalanced_execution import (
    ALLOWED_JUDGES,
    HARD_CAP_USD,
    PLANNED_PASSES,
    PLANNED_UNITS,
    CounterbalancedObservation,
    analyze_counterbalanced_observations,
    load_preflight_manifest,
    validate_preflight_manifest,
)


def test_frozen_preflight_has_the_exact_rq6_execution_shape():
    manifest = load_preflight_manifest()
    result = validate_preflight_manifest(manifest)
    assert result["ok"] is True
    assert result["units"] == PLANNED_UNITS
    assert result["passes"] == PLANNED_PASSES
    assert (result["same_family_slot_a"], result["same_family_slot_b"]) == (480, 480)
    assert set(result["per_judge_units"]) == set(ALLOWED_JUDGES)
    assert sum(balance["same"] for balance in result["human_reference_balance"].values()) == 240
    assert sum(balance["other"] for balance in result["human_reference_balance"].values()) == 240


def test_deepseek_or_a_non_ab_ba_schedule_is_rejected_before_execution():
    manifest = load_preflight_manifest()
    deepseek = copy.deepcopy(manifest)
    deepseek["units"][0]["judge_name"] = "deepseek/deepseek-chat"
    assert any("unsupported_or_excluded_judge" in error for error in validate_preflight_manifest(deepseek)["errors"])
    unswapped = copy.deepcopy(manifest)
    unswapped["units"][0]["passes"] = unswapped["units"][0]["passes"][:1]
    assert any("missing_ab_ba_schedule" in error for error in validate_preflight_manifest(unswapped)["errors"])


def _profile(max_usd: Decimal) -> RealExecutionProfile:
    return RealExecutionProfile(
        execution_mode="REAL", authorization_token="fixture", dataset_version_id="fixture",
        manifest_ids=("fixture",), manifest_hashes=("fixture",), source_commit="fixture", source_tag="fixture",
        pricing_version="pricing-config-v1", routing_version="fixture", routing_fingerprint="fixture",
        prompt_version="fixture", prompt_sha256="fixture", retry_policy_version="fixture", failure_policy_version="fixture",
        analysis_version="fixture", model_ids=("gpt-4o-mini",), configured_upstreams=(),
        caps=ExecutionCaps(PLANNED_PASSES, PLANNED_PASSES, 1_000_000, 1_000_000, max_usd),
    )


def _request() -> EvaluationRequest:
    return EvaluationRequest(
        question="Question", answer_a="Answer A", answer_b="Answer B", judge_name="gpt-4o-mini",
        provider=Provider.OPENAI, requested_model="gpt-4o-mini", temperature=0.0, top_p=1.0, seed=SEED,
        prompt_template_version="controlled-judge-pairwise-v1", experiment_id=UUID(int=1), controlled_unit_id=UUID(int=2),
        repetition_index=0, pass_number=1, original_answer_a_id=1, original_answer_b_id=2,
        presented_answer_a_id=1, presented_answer_b_id=2,
    )


SEED = 20260818


def test_hard_cap_blocks_before_a_second_provider_reservation():
    request = _request()
    single = BudgetLedger(_profile(Decimal("0.000001")))
    with pytest.raises(PermissionError):
        single.reserve(run_id="run", request=request)
    ledger = BudgetLedger(_profile(HARD_CAP_USD))
    ledger.reserve(run_id="run", request=request)
    assert ledger.snapshot()["reserved_usd"] != "0"


def test_preregistered_analysis_keeps_unstable_and_tie_outcomes_explicit():
    rows = [
        CounterbalancedObservation("1", "gpt-4o-mini", "HUMAN_PREFERS_SAME_FAMILY", "ANSWER_A", "SAME", "SAME"),
        CounterbalancedObservation("2", "gpt-4o-mini", "HUMAN_PREFERS_OTHER_FAMILY", "ANSWER_B", "OTHER", "OTHER"),
        CounterbalancedObservation("3", "anthropic/claude-3-haiku", "HUMAN_PREFERS_SAME_FAMILY", "ANSWER_A", "SAME", "OTHER"),
        CounterbalancedObservation("4", "meta-llama/llama-3.3-70b-instruct", "HUMAN_PREFERS_OTHER_FAMILY", "ANSWER_B", "TIE", "TIE"),
    ]
    metrics = analyze_counterbalanced_observations(rows, iterations=30)
    assert metrics["stable_same_family_preference"].value == 0.5
    assert metrics["valid_stable_decisive_coverage"].value == 0.5
    assert metrics["order_sensitive_disagreement"].value == 1 / 3
    assert metrics["tie_or_abstention_rate"].value == 0.25
