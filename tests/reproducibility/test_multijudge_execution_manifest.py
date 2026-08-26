"""Provider-free verification of the frozen multi-judge execution manifest."""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

from backend.multijudge.manifest import build_manifest, validate_manifest


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "evidence" / "multijudge_consensus" / "execution_manifest_v1.json"
PROTOCOL_PATH = ROOT / "evidence" / "multijudge_consensus" / "protocol_v1.json"
EXPECTED_MANIFEST_SHA256 = "6c2fa4a926e458c598c73604daa1b69d766bc5b2d04853e73c3a35bf9017e351"


@lru_cache(maxsize=1)
def manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_reconstructs_deterministically_from_the_immutable_release_dump():
    frozen = manifest()
    rebuilt = build_manifest(created_at=frozen["created_at"])
    assert rebuilt == frozen
    assert hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest() == EXPECTED_MANIFEST_SHA256


def test_population_is_exactly_the_frozen_1611_pair_reference_lineage():
    frozen = manifest()
    population = frozen["population"]
    assert population["n_planned_pairs"] == 1611
    assert population["exclusions"] == {
        "human_preference_records": 2396,
        "unordered_reference_groups": 1814,
        "conflicting_unordered_groups_excluded": 199,
        "non_conflicting_canonical_pairs": 1615,
        "blank_answer_pairs_excluded": 4,
        "eligible_execution_pairs": 1611,
    }
    assert population["category_distribution"] == {"coding": 199, "extraction": 201, "humanities": 194, "math": 193, "reasoning": 204, "roleplay": 217, "stem": 214, "writing": 189}
    assert len(frozen["pairs"]) == len({pair["canonical_pair_id"] for pair in frozen["pairs"]}) == 1611
    assert all(pair["original_answer_1_id"] < pair["original_answer_2_id"] for pair in frozen["pairs"])


def test_schedule_counterbalance_identity_and_routes_are_complete():
    frozen = manifest(); passes = frozen["planned_passes"]
    assert len(passes) == 6444
    assert len({row["idempotency_key"] for row in passes}) == 6444
    by_pair = defaultdict(list)
    for row in passes:
        by_pair[row["canonical_pair_id"]].append(row)
        expected = (row["original_answer_1_id"], row["original_answer_2_id"]) if row["presentation"] == "AB" else (row["original_answer_2_id"], row["original_answer_1_id"])
        assert (row["displayed_A_answer_id"], row["displayed_B_answer_id"]) == expected
    assert all(len(rows) == 4 and Counter(row["presentation"] for row in rows) == {"AB": 2, "BA": 2} for rows in by_pair.values())
    assert frozen["accounting"]["global_presentations"] == {"AB": 3222, "BA": 3222}
    assert all(sorted(counts.values()) == [805, 806] for counts in frozen["accounting"]["per_judge_presentations"].values())
    assert [row["route"] for row in frozen["scientific_configuration"]["judges"]] == ["OPENAI_DIRECT", "amazon-bedrock", "streamlake", "deepinfra/turbo"]
    assert all(row["fallbacks_allowed"] is False for row in frozen["scientific_configuration"]["judges"])


def test_protocol_linkage_safety_and_execution_lock_hold():
    frozen = manifest()
    assert frozen["protocol_sha256"] == hashlib.sha256(PROTOCOL_PATH.read_bytes()).hexdigest()
    assert frozen["execution_authorized"] is False
    assert frozen["population"]["human_reference_outcome_in_manifest"] is False
    assert frozen["evidence_class_safety"]["excluded_inputs"] == ["PILOT", "SUPERSEDED", "legacy exploratory decisions", "Live Evaluation", "qualitative CSV judgments", "manually edited judgments"]
    assert "winner_id" not in json.dumps(frozen)
    validate_manifest(frozen)
