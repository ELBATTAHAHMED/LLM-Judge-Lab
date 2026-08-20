from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from reliability_metrics import AlignmentObservation, RepetitionObservation, SwapObservation, rq1_alignment, rq2_consistency, rq3_position_sensitivity, rq6_source_family_preference, rq7_mitigation_comparison
from experiment_planning import PairRecord, call_plan, generate_units, manifest, validate_units
from experiment_protocols import PROTOCOLS, SCIENTIFIC_TERMINOLOGY
from controlled_transforms import make_format_variant, make_verbosity_variant, validate_format_variant, validate_verbosity_variant


def pair(pid=1, a_model="gpt-4", b_model="claude-v1", label="ANSWER_A"):
    return PairRecord(pid, 10, pid * 10 + 1, pid * 10 + 2, "A fact.", "B fact.", a_model, b_model, "writing", label)


def test_rq1_agreement_ties_missing_reference_and_exclusions():
    result = rq1_alignment([AlignmentObservation("ANSWER_A", "ANSWER_A"), AlignmentObservation("ANSWER_B", "ANSWER_A"), AlignmentObservation("TIE", "TIE"), AlignmentObservation(None, "ANSWER_A"), AlignmentObservation("ANSWER_A", "TIMEOUT")])
    assert result["eligible_n"] == 3 and result["exact_agreement"] == 2 / 3
    assert result["human_tie_count"] == result["judge_tie_count"] == result["tie_agreement_count"] == 1
    assert result["exclusions"] == {"missing_human_reference": 1, "judge_timeout": 1}


def test_rq2_pair_level_repetitions_and_temperature_are_not_merged():
    records = [RepetitionObservation("pair-a-t0", 1, 1, 2, "gpt", 0.0, i, 4, "ANSWER_A") for i in range(5)]
    records += [RepetitionObservation("pair-b-t0", 1, 3, 4, "gpt", 0.0, i, 0, "ANSWER_B") for i in range(5)]
    records += [RepetitionObservation("pair-a-t7", 1, 1, 2, "gpt", 0.7, i, 0, "ANSWER_A") for i in range(5)]
    result = rq2_consistency(records)
    assert result["eligible_group_n"] == 3
    assert {g["n_repetitions"] for g in result["groups"]} == {5}
    assert {g["temperature"] for g in result["groups"]} == {0.0, 0.7}
    assert next(g for g in result["groups"] if g["group_key"] == "pair-a-t0")["retry_count_total"] == 20


def test_rq3_true_flip_tie_disagreement_incomplete_and_slot_imbalance_are_distinct():
    result = rq3_position_sensitivity([
        SwapObservation("flip", "AB", "ANSWER_A", "A"), SwapObservation("flip", "BA", "ANSWER_B", "A"),
        SwapObservation("tie", "AB", "ANSWER_A", "A"), SwapObservation("tie", "BA", "TIE", None),
        SwapObservation("incomplete", "AB", "ANSWER_A", "A"),
    ])
    assert result["classifications"] == {"DECISIVE_FLIP": 1, "TIE_DISAGREEMENT": 1}
    assert result["eligible_paired_n"] == 2 and result["incomplete_pair_count"] == 1
    assert result["paired_decisive_flip_rate"] == 1.0 and result["slot_win_imbalance"] == 1.0


def test_rq4_exact_duplicate_variant_is_longer_linked_and_rejects_addition():
    original = "A fact."
    variant = make_verbosity_variant(original)
    valid = validate_verbosity_variant(1, original, variant)
    invalid = validate_verbosity_variant(1, original, variant + " New fact.")
    assert valid.valid and valid.variant_word_count > valid.source_word_count and valid.source_checksum != valid.variant_checksum
    assert not invalid.valid


def test_rq5_format_equivalence_balanced_design_and_semantic_addition_rejected():
    original = "First fact.\nSecond fact."
    variant = make_format_variant(original)
    assert validate_format_variant(1, original, variant).valid
    assert not validate_format_variant(1, original, variant + "\n- New claim.").valid
    units = generate_units([pair(1), pair(2)], "RQ5", limit=2, snapshot_id="s")
    assert {u.presentation_order for u in units} == {"AB_BA"} and all(u.pass_count == 2 for u in units)


def test_rq6_source_metadata_self_other_balancing_and_no_aslot_only_comparator():
    rows = [pair(1, "gpt-4", "claude-v1"), pair(2, "gpt-4", "llama-13b")]
    units = generate_units(rows, "RQ6", limit=2, snapshot_id="s")
    gpt = [u for u in units if u.judge_name == "gpt-4o-mini"]
    assert {u.presentation_order for u in gpt} == {"SELF_A", "SELF_B"}
    metric = rq6_source_family_preference([{"winner_family": "OPENAI", "self_family": "OPENAI", "other_family": "ANTHROPIC", "self_slot": "A"}, {"winner_family": "ANTHROPIC", "self_family": "OPENAI", "other_family": "ANTHROPIC", "self_slot": "B"}])
    assert metric["position_balanced"] and metric["self_family_preference_rate"] == 0.5


def test_rq7_matches_strategies_and_keeps_negative_and_no_data_honest():
    negative = rq7_mitigation_comparison({"pair-1": 0.9}, {"pair-1": 0.6})
    assert negative == {"status": "ESTIMABLE", "matched_n": 1, "changes": {"pair-1": -0.30000000000000004}}
    assert rq7_mitigation_comparison({"a": 1.0}, {"b": 1.0})["status"] == "NOT_ESTIMABLE"
    units = generate_units([pair(1), pair(2)], "RQ7", limit=2, snapshot_id="s")
    assert validate_units(units) == [] and sum(u.calls for u in units) == 2 * 4 * 3


def test_protocols_manifest_stability_duplicate_detection_and_call_count_correctness():
    rows = [pair(1), pair(2), pair(3)]
    first, second = generate_units(rows, "RQ3", limit=3, snapshot_id="frozen"), generate_units(rows, "RQ3", limit=3, snapshot_id="frozen")
    assert first == second and manifest("RQ3", first, "frozen")["manifest_sha256"] == manifest("RQ3", second, "frozen")["manifest_sha256"]
    assert validate_units(first + [first[0]]) == ["duplicate_unit_id"]
    plan = call_plan(rows, limit=3, snapshot_id="frozen")
    assert plan["RQ3"]["planned_calls"] == 3 * 4 * 2
    assert set(PROTOCOLS) == {f"RQ{i}" for i in range(1, 8)}
    assert SCIENTIFIC_TERMINOLOGY["Ground Truth"] == "Human Preference Reference Labels"
