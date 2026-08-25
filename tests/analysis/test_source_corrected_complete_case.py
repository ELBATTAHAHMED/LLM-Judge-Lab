"""Focused provider-free guards for complete-case source-corrected analysis."""
from __future__ import annotations

from analyze_source_corrected_complete_case import _presented_to_canonical, _variant_outcome


def test_position_mapping_restores_original_answer_identity() -> None:
    assert _presented_to_canonical("ANSWER_A", "AB") == "ANSWER_A"
    assert _presented_to_canonical("ANSWER_A", "BA") == "ANSWER_B"
    assert _presented_to_canonical("ANSWER_B", "BA") == "ANSWER_A"
    assert _presented_to_canonical("TIE", "BA") == "TIE"


def test_variant_mapping_never_uses_a_presented_slot_as_an_original_identity() -> None:
    assert _variant_outcome("ANSWER_A", "AB") == "ORIGINAL"
    assert _variant_outcome("ANSWER_B", "AB") == "VARIANT"
    assert _variant_outcome("ANSWER_A", "BA") == "VARIANT"
    assert _variant_outcome("ANSWER_B", "BA") == "ORIGINAL"
    assert _variant_outcome("UNKNOWN", "AB") is None
