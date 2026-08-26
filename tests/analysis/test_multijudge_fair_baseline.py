"""Provider-free unit tests for Phase 9's independent matched comparison."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from backend.multijudge.fair_baseline import (  # noqa: E402
    FairBaselineValidationError,
    frozen_consensus,
    percentile_bootstrap,
    retained_pair_set_checksum,
)


def test_retained_pair_checksum_is_order_independent_but_identity_sensitive():
    assert retained_pair_set_checksum(["pair-b", "pair-a"]) == retained_pair_set_checksum(["pair-a", "pair-b"])
    assert retained_pair_set_checksum(["pair-a", "pair-b"]) != retained_pair_set_checksum(["pair-a", "pair-c"])


def test_retained_pair_checksum_rejects_duplicate_pair_identity():
    with pytest.raises(FairBaselineValidationError):
        retained_pair_set_checksum(["pair-a", "pair-a"])


def test_independent_frozen_rule_retains_supermajority_including_tie():
    assert frozen_consensus(["TIE", "TIE", "TIE", "ORIGINAL_ANSWER_1"]) == "TIE"
    assert frozen_consensus(["ORIGINAL_ANSWER_2"] * 4) == "ORIGINAL_ANSWER_2"


def test_independent_frozen_rule_abstains_on_both_split_patterns():
    assert frozen_consensus(["ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_2", "ORIGINAL_ANSWER_2"]) is None
    assert frozen_consensus(["ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_2", "TIE"]) is None


def test_frozen_bootstrap_is_reproducible_without_resampling_judges_separately():
    assert percentile_bootstrap([1.0, 0.5, 0.0]) == percentile_bootstrap([1.0, 0.5, 0.0])


def test_structural_consensus_cannot_receive_human_reference_or_correctness_inputs():
    assert tuple(inspect.signature(frozen_consensus).parameters) == ("votes",)
