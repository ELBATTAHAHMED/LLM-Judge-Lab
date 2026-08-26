"""Provider-free guardrails for the Phase 10 comparability audit."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from backend.analysis.mitigation_comparison import ComparisonError, bootstrap, key, multi_consensus, set_digest  # noqa: E402


def test_immutable_pair_key_is_order_invariant_for_answer_ids():
    assert key("dataset", 9, 12, 3) == key("dataset", 9, 3, 12)


def test_overlap_checksum_is_deterministic_and_rejects_duplicates():
    assert set_digest(["b", "a"]) == set_digest(["a", "b"])
    with pytest.raises(ComparisonError):
        set_digest(["a", "a"])


def test_multi_judge_rule_keeps_tie_and_abstains_on_split():
    assert multi_consensus(["TIE", "TIE", "TIE", "ORIGINAL_ANSWER_1"]) == "TIE"
    assert multi_consensus(["ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_2", "TIE"]) is None


def test_dualswap_bootstrap_is_seed_deterministic_at_pair_by_judge_unit_level():
    assert bootstrap([0, 1, -1]) == bootstrap([0, 1, -1])
