"""Frozen RQ7 raw-evidence metric matrix (no provider calls)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from phase4_metrics import RQ7Observation, analyze_rq7


def row(key, human="ANSWER_A", baseline="ANSWER_A", ab="ANSWER_A", ba="ANSWER_A"):
    return RQ7Observation("CONTROLLED", key, "RQ7", "gpt-4o-mini", "MATCHED", key, human, baseline, ab, ba)


def test_rq7_preserves_improvement_worsening_and_trade_off_signs():
    # Agreement rises 0.5 -> 1.0, while dual-pass disagreement is nonzero.
    improved = analyze_rq7([row("a", "ANSWER_A", "ANSWER_B", "ANSWER_A", "ANSWER_A"), row("b", "ANSWER_B", "ANSWER_B", "ANSWER_B", "ANSWER_A")], iterations=20)
    assert improved["agreement_delta"].value > 0
    assert improved["dual_swap_dual_pass_disagreement"].value == 0.5
    # Agreement falls despite position stability improving (a real trade-off).
    worsened = analyze_rq7([row("c", "ANSWER_A", "ANSWER_A", "ANSWER_B", "ANSWER_B"), row("d", "ANSWER_B", "ANSWER_B", "ANSWER_A", "ANSWER_A")], iterations=20)
    assert worsened["agreement_delta"].value < 0


def test_rq7_ties_failures_missing_second_and_not_estimable_are_visible():
    result = analyze_rq7([
        row("tie", "TIE", "TIE", "TIE", "TIE"),
        row("failure", "ANSWER_A", "API_ERROR", "API_ERROR", "API_ERROR"),
        row("missing", "ANSWER_A", "ANSWER_A", "ANSWER_A", None),
    ], iterations=20)
    assert result["baseline_tie_rate"].value == 0.5
    assert result["dual_swap_failure_rate"].value > 0
    assert result["agreement_delta"].status == "ESTIMABLE"
    kappa = analyze_rq7([row("only", "ANSWER_A", "ANSWER_A", "ANSWER_A", "ANSWER_A")], iterations=20)
    assert kappa["baseline_cohens_kappa"].status == "NOT_ESTIMABLE"


def test_rq7_zero_comparable_units_never_becomes_zero_effect():
    result = analyze_rq7([row("x", "ANSWER_A", "API_ERROR", "API_ERROR", None)], iterations=20)
    assert result["agreement_delta"].value is None
    assert result["agreement_delta"].status == "NOT_ESTIMABLE"
