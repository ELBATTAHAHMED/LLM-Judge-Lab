"""Pure provider-free checks for the frozen Phase 8 consensus rule."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from analyze_multijudge_consensus import (  # noqa: E402
    JUDGES,
    MultiJudgeAnalysisError,
    _matched_comparator,
    bootstrap_percentile,
    consensus_for_four,
    consensus_for_three,
    pair_delta,
)


def test_frozen_four_judge_rule_accepts_only_supermajorities_and_tie_is_a_class():
    assert consensus_for_four(["TIE", "TIE", "TIE", "ORIGINAL_ANSWER_1"]).label == "TIE"
    assert consensus_for_four(["ORIGINAL_ANSWER_2"] * 4).pattern == "4-0"
    with pytest.raises(MultiJudgeAnalysisError):
        consensus_for_four(["ORIGINAL_ANSWER_1"] * 3)


def test_four_judge_split_patterns_abstain_without_human_tie_breaking():
    assert consensus_for_four(["ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_2", "ORIGINAL_ANSWER_2"]).label is None
    assert consensus_for_four(["ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_2", "TIE"]).label is None


def test_matched_comparator_uses_the_exact_retained_population_for_every_judge():
    records = [
        {"consensus_label": "ORIGINAL_ANSWER_1", "human_reference": "ORIGINAL_ANSWER_1", "votes": dict.fromkeys(JUDGES, "ORIGINAL_ANSWER_1")},
        {
            "consensus_label": "ORIGINAL_ANSWER_2",
            "human_reference": "ORIGINAL_ANSWER_1",
            "votes": dict(zip(JUDGES, ["ORIGINAL_ANSWER_2", "ORIGINAL_ANSWER_2", "ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_1"])),
        },
    ]
    result = _matched_comparator(records, JUDGES)
    assert result["n"] == 2
    assert {row["n"] for row in result["per_judge"].values()} == {2}
    assert result["equal_weight_agreement"] == 0.75


def test_pair_delta_is_calculated_at_the_pair_level_before_averaging():
    assert pair_delta("ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_1", ["ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_2", "TIE", "ORIGINAL_ANSWER_1"]) == 0.5


def test_primary_bootstrap_is_reproducible_with_the_frozen_seed():
    values = [0.0, 1.0, 1.0, 0.25]
    assert bootstrap_percentile(values, resamples=200) == bootstrap_percentile(values, resamples=200)


def test_three_judge_sensitivity_is_separate_from_the_primary_rule():
    assert consensus_for_three(["TIE", "TIE", "ORIGINAL_ANSWER_1"]).label == "TIE"
    assert consensus_for_three(["ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_2", "TIE"]).label is None
    with pytest.raises(MultiJudgeAnalysisError):
        consensus_for_four(["TIE", "TIE", "ORIGINAL_ANSWER_1"])


def test_consensus_construction_cannot_receive_a_human_reference_label():
    assert tuple(inspect.signature(consensus_for_four).parameters) == ("votes",)
