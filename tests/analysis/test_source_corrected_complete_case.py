"""Focused provider-free guards for complete-case source-corrected analysis."""
from __future__ import annotations

from types import SimpleNamespace

from backend.analysis.source_corrected_complete_case import (
    LogicalPass,
    _by_rq,
    _presented_to_canonical,
    _variant_outcome,
)
from backend.analysis.source_corrected_full_population import CONTROLLED_SEED, MULTIJUDGE_SEED
from backend.core.final_evidence import CANONICAL_FINAL_MANIFESTS


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


def test_full_population_selector_includes_reusable_rows_once() -> None:
    unit = SimpleNamespace(manifest_id=CANONICAL_FINAL_MANIFESTS["RQ1"])
    rows = [
        LogicalPass("controlled:reusable:1", unit, "RQ1", "BASELINE", "judge", "AB", "ANSWER_A", "SOURCE_CORRECT_REUSABLE"),
        LogicalPass("controlled:corrected:1", unit, "RQ1", "BASELINE", "judge", "AB", "ANSWER_A", "CORRECTED_ORIGINAL"),
    ]
    assert [row.historical_identity for row in _by_rq(rows, "RQ1")] == ["controlled:corrected:1"]
    assert [row.historical_identity for row in _by_rq(rows, "RQ1", include_reusable=True)] == [
        "controlled:reusable:1", "controlled:corrected:1"
    ]


def test_full_population_analysis_uses_the_frozen_seed_assignments() -> None:
    assert CONTROLLED_SEED == 20260818
    assert MULTIJUDGE_SEED == 20260823
