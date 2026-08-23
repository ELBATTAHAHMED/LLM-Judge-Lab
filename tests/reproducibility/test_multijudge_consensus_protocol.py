"""Offline checks for the frozen pre-execution multi-judge protocol."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = ROOT / "evidence" / "multijudge_consensus" / "protocol_v1.json"
EXPECTED_SHA256 = "819f2e2dea8fb32e4c32000551d6048a16ecc8d28f1bb32d2cce4d02a15c40ce"
VALID = {"ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_2", "TIE"}


def protocol() -> dict:
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def primary(votes: list[str]) -> str:
    if len(votes) != 4 or any(vote not in VALID for vote in votes):
        return "NO_CONSENSUS_OPERATIONAL"
    return "CONSENSUS" if max(Counter(votes).values()) >= 3 else "NO_CONSENSUS_SPLIT"


def sensitivity(votes: list[str]) -> str:
    if len(votes) != 3 or any(vote not in VALID for vote in votes):
        return "NOT_APPLICABLE"
    return "CONSENSUS" if max(Counter(votes).values()) >= 2 else "NO_CONSENSUS_SPLIT"


def map_displayed(displayed: str, presented_a: int, presented_b: int, original_1: int, original_2: int) -> str:
    if displayed == "TIE":
        return "TIE"
    answer_id = presented_a if displayed == "A" else presented_b if displayed == "B" else None
    if answer_id == original_1:
        return "ORIGINAL_ANSWER_1"
    if answer_id == original_2:
        return "ORIGINAL_ANSWER_2"
    raise ValueError("non-vote or incompatible original-answer identity")


def test_protocol_identity_population_and_integrity_are_frozen():
    body = protocol()
    assert body["protocol_id"] == "multi-judge-consensus-v1"
    assert body["status"] == "FROZEN_PRE_EXECUTION_PROTOCOL"
    assert body["provider_execution"] == "NOT_YET_AUTHORIZED"
    assert body["population"]["n_planned_pairs"] == 1611
    assert body["execution_plan"]["planned_scientific_passes"] == 6444
    assert len(body["judges"]) == 4
    assert hashlib.sha256(PROTOCOL_PATH.read_bytes()).hexdigest() == EXPECTED_SHA256


def test_primary_rule_preserves_ties_and_rejects_incomplete_or_plurality_votes():
    assert primary(["ORIGINAL_ANSWER_1"] * 4) == "CONSENSUS"  # 4-0
    assert primary(["ORIGINAL_ANSWER_1"] * 3 + ["ORIGINAL_ANSWER_2"]) == "CONSENSUS"  # 3-1
    assert primary(["ORIGINAL_ANSWER_1"] * 2 + ["ORIGINAL_ANSWER_2"] * 2) == "NO_CONSENSUS_SPLIT"  # 2-2
    assert primary(["ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_2", "TIE"]) == "NO_CONSENSUS_SPLIT"  # 2-1-1
    assert primary(["TIE", "TIE", "TIE", "ORIGINAL_ANSWER_1"]) == "CONSENSUS"
    assert primary(["ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_2", "TIE"]) == "NO_CONSENSUS_OPERATIONAL"
    assert primary(["ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_2", "TIE", "UNKNOWN"]) == "NO_CONSENSUS_OPERATIONAL"


def test_three_valid_sensitivity_is_separate_and_requires_a_majority():
    body = protocol()
    assert body["three_valid_judge_sensitivity"]["never_replaces_primary"] is True
    assert sensitivity(["ORIGINAL_ANSWER_1"] * 3) == "CONSENSUS"
    assert sensitivity(["TIE", "TIE", "ORIGINAL_ANSWER_2"]) == "CONSENSUS"
    assert sensitivity(["ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_2", "TIE"]) == "NO_CONSENSUS_SPLIT"


def test_display_mapping_uses_original_ids_and_no_human_reference_tie_breaking():
    assert map_displayed("A", 10, 20, 10, 20) == "ORIGINAL_ANSWER_1"
    assert map_displayed("A", 20, 10, 10, 20) == "ORIGINAL_ANSWER_2"
    assert map_displayed("B", 20, 10, 10, 20) == "ORIGINAL_ANSWER_1"
    assert map_displayed("TIE", 20, 10, 10, 20) == "TIE"
    try:
        map_displayed("A", 30, 10, 10, 20)
    except ValueError:
        pass
    else:
        raise AssertionError("an unknown answer identity must fail closed")
    body = protocol()
    prohibited = body["population"]["human_reference_prohibitions"] + body["primary_consensus"]["forbidden"]
    assert "presentation assignment" in prohibited
    assert "human-reference tie-break" in prohibited


def test_fixed_seed_assignment_constraints_and_bootstrap_are_unambiguous():
    body = protocol()
    assignment = body["presentation_assignment"]
    assert assignment["seed"] == 20260823
    assert assignment["per_judge_target"] == {"AB": [805, 806], "BA": [805, 806]}
    assert "Exactly two judges receive AB" in assignment["per_pair_constraint"]
    assert body["uncertainty"] == {
        "statistical_unit": "canonical answer pair",
        "bootstrap": "pair-level nonparametric percentile bootstrap",
        "resamples": 10000,
        "confidence_level": 0.95,
        "seed": 20260823,
        "metrics": ["consensus agreement", "coverage", "primary matched agreement delta"],
        "matched_delta_resampling": "Resample complete pair-level comparison records, preserving all four votes and the consensus result together.",
        "forbidden": "Do not bootstrap individual passes independently."
    }
