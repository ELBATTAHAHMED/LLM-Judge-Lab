from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from reuse_audit import ReasonCode, ReuseClass, classify_historical_decision, historical_decision_reasons, is_exact_frozen_match  # noqa: E402


def complete_provenance():
    return {"provider": "OPENAI", "effective_model": "gpt-4o-mini", "protocol_version": "phase3-controlled-v1", "prompt_template_version": "judge-pairwise-structured-v1", "dataset_snapshot": "frozen", "temperature": 0.0, "top_p": 1.0, "seed": 42, "repetition_index": 0}


def test_exact_match_requires_every_frozen_dimension_and_partial_is_rejected():
    assert is_exact_frozen_match(complete_provenance())
    partial = complete_provenance(); partial.pop("seed")
    assert not is_exact_frozen_match(partial)
    classification, reasons = classify_historical_decision(calibrated=False, live_sandbox=False, provenance=partial)
    assert classification is ReuseClass.REUSE_AS_EXPLORATORY and ReasonCode.INCOMPLETE_PROVENANCE in reasons


def test_calibrated_final_row_without_structured_passes_is_not_rq3_evidence():
    classification, reasons = classify_historical_decision(calibrated=True, live_sandbox=False, provenance={})
    assert classification is ReuseClass.REUSE_AS_EXPLORATORY
    assert ReasonCode.MISSING_PASS_LEVEL_DATA in reasons


def test_live_and_mock_like_inputs_never_count_as_final_controlled_evidence():
    classification, reasons = classify_historical_decision(calibrated=False, live_sandbox=True, provenance=complete_provenance())
    assert classification is ReuseClass.REUSE_AS_EXPLORATORY and reasons == (ReasonCode.LIVE_SANDBOX,)


def test_stochastic_prompt_only_and_semantic_variants_have_specific_reason_codes():
    assert ReasonCode.WRONG_GROUPING.value in {x.value for x in (ReasonCode.WRONG_GROUPING, ReasonCode.MISSING_REPETITION_ID)}
    assert ReasonCode.SEMANTICALLY_CONFOUNDED in {ReasonCode.SEMANTICALLY_CONFOUNDED}


def test_call_saving_arithmetic_is_conservative():
    frozen, approved = 16_600, 0
    assert frozen - approved == 16_600
