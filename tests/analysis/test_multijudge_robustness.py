"""Provider-free Phase 11 sensitivity guardrails."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from backend.multijudge.robustness import JUDGES, RobustnessError, boot, evaluate  # noqa: E402


def row(votes, human="ORIGINAL_ANSWER_1"):
    return {"votes": dict(zip(JUDGES, votes)), "human_reference": human}


def test_primary_rule_and_equal_weights_are_preserved():
    result = evaluate([row(["ORIGINAL_ANSWER_1"] * 4)], JUDGES, rule="four", label="PRIMARY")
    assert result["retained_n"] == 1 and result["delta"] == 0 and not result["sensitivity_only"]


def test_leave_one_out_uses_exactly_three_judges():
    judges = tuple(judge for judge in JUDGES if judge != JUDGES[0])
    result = evaluate([row(["TIE", "TIE", "TIE", "ORIGINAL_ANSWER_1"], "TIE")], judges, rule="three", label="OMIT")
    assert len(result["judges"]) == 3 and result["retained_n"] == 1


def test_unanimity_does_not_accept_three_of_four():
    with pytest.raises(RobustnessError):
        evaluate([row(["TIE", "TIE", "TIE", "ORIGINAL_ANSWER_1"], "TIE")], JUDGES, rule="unanimity", label="STRICT")


def test_tie_is_a_valid_unanimity_class():
    result = evaluate([row(["TIE"] * 4, "TIE")], JUDGES, rule="unanimity", label="STRICT")
    assert result["agreement"] == 1


def test_bootstrap_is_deterministic():
    assert boot([0.0, 0.25, 1.0]) == boot([0.0, 0.25, 1.0])
