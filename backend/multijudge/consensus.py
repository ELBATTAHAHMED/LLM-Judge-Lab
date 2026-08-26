"""Provider-free Phase 8 analysis for the frozen multi-judge consensus protocol.

This module deliberately keeps consensus construction independent of human
reference labels.  Labels are attached only after the frozen vote rule has
selected its retained population.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.multijudge.manifest import _copy_rows
from backend.core.database import SessionLocal
from backend.multijudge.models import MultiJudgeExecutionBatch, MultiJudgeExecutionSlot


ROOT = Path(__file__).resolve().parent.parent.parent
PROTOCOL_PATH = ROOT / "evidence" / "multijudge_consensus" / "protocol_v1.json"
MANIFEST_PATH = ROOT / "evidence" / "multijudge_consensus" / "execution_manifest_v1.json"
INTEGRITY_PATH = ROOT / "evidence" / "multijudge_consensus" / "postexecution_integrity_v1.json"
OUTPUT_PATH = ROOT / "evidence" / "multijudge_consensus" / "primary_analysis_v1.json"
EXPECTED_PROTOCOL_SHA256 = "819f2e2dea8fb32e4c32000551d6048a16ecc8d28f1bb32d2cce4d02a15c40ce"
EXPECTED_MANIFEST_SHA256 = "6c2fa4a926e458c598c73604daa1b69d766bc5b2d04853e73c3a35bf9017e351"
EXPECTED_INTEGRITY_SHA256 = "9e0273c0b51917ba2ea8358c1d29041f8ed3eacd93d33839b8ebafe6b7cf4ba3"
JUDGES = (
    "gpt-4o-mini",
    "anthropic/claude-3-haiku",
    "deepseek/deepseek-chat",
    "meta-llama/llama-3.3-70b-instruct",
)
VALID_VOTES = frozenset({"ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_2", "TIE"})
BOOTSTRAP_SEED = 20260823
BOOTSTRAP_RESAMPLES = 10_000


class MultiJudgeAnalysisError(RuntimeError):
    pass


@dataclass(frozen=True)
class ConsensusDecision:
    pattern: str
    label: str | None

    @property
    def covered(self) -> bool:
        return self.label is not None


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def consensus_for_four(votes: Iterable[str]) -> ConsensusDecision:
    """Frozen primary rule: only 3-of-4 or 4-of-4 produces consensus."""
    values = tuple(votes)
    if len(values) != 4 or any(value not in VALID_VOTES for value in values):
        raise MultiJudgeAnalysisError("primary consensus requires exactly four valid scientific votes")
    counts = Counter(values)
    top_label, top_count = counts.most_common(1)[0]
    if top_count == 4:
        return ConsensusDecision("4-0", top_label)
    if top_count == 3:
        return ConsensusDecision("3-1", top_label)
    if len(counts) == 2:
        return ConsensusDecision("2-2", None)
    if sorted(counts.values()) == [1, 1, 2]:
        return ConsensusDecision("2-1-1", None)
    raise MultiJudgeAnalysisError("unrecognised four-vote pattern")


def consensus_for_three(votes: Iterable[str]) -> ConsensusDecision:
    """Pre-registered sensitivity-only rule, isolated from the primary path."""
    values = tuple(votes)
    if len(values) != 3 or any(value not in VALID_VOTES for value in values):
        raise MultiJudgeAnalysisError("three-judge sensitivity requires exactly three valid votes")
    counts = Counter(values)
    top_label, top_count = counts.most_common(1)[0]
    if top_count == 3:
        return ConsensusDecision("3-0", top_label)
    if top_count == 2:
        return ConsensusDecision("2-1", top_label)
    return ConsensusDecision("1-1-1", None)


def bootstrap_percentile(values: Iterable[float], *, seed: int = BOOTSTRAP_SEED, resamples: int = BOOTSTRAP_RESAMPLES) -> dict[str, float | int]:
    """Pair-level nonparametric percentile bootstrap, deliberately deterministic."""
    array = np.asarray(tuple(values), dtype=float)
    if array.size == 0:
        raise MultiJudgeAnalysisError("cannot bootstrap an empty pair-level metric")
    rng = np.random.default_rng(seed)
    samples = np.empty(resamples, dtype=float)
    for index in range(resamples):
        samples[index] = array[rng.integers(0, array.size, size=array.size)].mean()
    low, high = np.percentile(samples, [2.5, 97.5])
    return {"estimate": float(array.mean()), "ci_low": float(low), "ci_high": float(high), "n": int(array.size)}


def pair_delta(consensus_label: str, human_reference: str, judge_votes: Iterable[str]) -> float:
    """Frozen matched delta: consensus correctness minus equal-weight individual correctness."""
    votes = tuple(judge_votes)
    if len(votes) not in {3, 4} or consensus_label not in VALID_VOTES or human_reference not in VALID_VOTES:
        raise MultiJudgeAnalysisError("matched delta requires valid consensus, reference, and judge votes")
    consensus_correct = float(consensus_label == human_reference)
    individual_mean = sum(vote == human_reference for vote in votes) / len(votes)
    return consensus_correct - individual_mean


def _load_frozen_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    protocol_sha, manifest_sha, integrity_sha = sha256_file(PROTOCOL_PATH), sha256_file(MANIFEST_PATH), sha256_file(INTEGRITY_PATH)
    if (protocol_sha, manifest_sha, integrity_sha) != (EXPECTED_PROTOCOL_SHA256, EXPECTED_MANIFEST_SHA256, EXPECTED_INTEGRITY_SHA256):
        raise MultiJudgeAnalysisError("frozen protocol, manifest, or integrity artifact SHA mismatch")
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    integrity = json.loads(INTEGRITY_PATH.read_text(encoding="utf-8"))
    if protocol.get("protocol_id") != "multi-judge-consensus-v1" or integrity.get("analysis_ready") is not True:
        raise MultiJudgeAnalysisError("frozen protocol identity or Phase 7 readiness is invalid")
    return protocol, manifest, integrity


def _reference_labels(manifest: dict[str, Any]) -> dict[str, str]:
    """Derive frozen unordered-pair reference labels only after vote construction."""
    grouped: dict[tuple[int, int, int], list[list[str | None]]] = defaultdict(list)
    for row in _copy_rows("human_preferences"):
        grouped[(int(row[1]), *sorted((int(row[2]), int(row[3]))))].append(row)
    labels: dict[str, str] = {}
    for pair in manifest["pairs"]:
        key = (int(pair["prompt_id"]), int(pair["original_answer_1_id"]), int(pair["original_answer_2_id"]))
        rows = grouped.get(key, [])
        if [int(row[0]) for row in sorted(rows, key=lambda item: int(item[0]))] != pair["human_reference_record_ids"]:
            raise MultiJudgeAnalysisError("human-reference provenance does not match frozen pair manifest")
        winners = {row[4] for row in rows}
        if len(winners) != 1:
            raise MultiJudgeAnalysisError("unordered human reference is not canonical")
        winner = next(iter(winners))
        labels[pair["canonical_pair_id"]] = (
            "TIE" if winner is None else "ORIGINAL_ANSWER_1" if int(winner) == int(pair["original_answer_1_id"]) else "ORIGINAL_ANSWER_2" if int(winner) == int(pair["original_answer_2_id"]) else "INVALID"
        )
        if labels[pair["canonical_pair_id"]] not in VALID_VOTES:
            raise MultiJudgeAnalysisError("human reference winner does not map to a canonical answer identity")
    return labels


def _ledger_votes(session: Session, manifest: dict[str, Any]) -> dict[str, list[MultiJudgeExecutionSlot]]:
    batch = session.scalar(select(MultiJudgeExecutionBatch).where(MultiJudgeExecutionBatch.manifest_sha256 == EXPECTED_MANIFEST_SHA256))
    if batch is None or batch.status != "COMPLETED":
        raise MultiJudgeAnalysisError("completed frozen multi-judge batch is unavailable")
    slots = list(session.scalars(select(MultiJudgeExecutionSlot).where(MultiJudgeExecutionSlot.batch_id == batch.id)))
    if len(slots) != 6444 or len({slot.planned_pass_id for slot in slots}) != 6444:
        raise MultiJudgeAnalysisError("durable ledger does not match frozen planned-slot identity")
    by_pair: dict[str, list[MultiJudgeExecutionSlot]] = defaultdict(list)
    for slot in slots:
        by_pair[slot.canonical_pair_id].append(slot)
    expected_pairs = {row["canonical_pair_id"] for row in manifest["pairs"]}
    if set(by_pair) != expected_pairs or any(
        len(rows) != len(JUDGES) or {slot.judge_id for slot in rows} != set(JUDGES)
        for rows in by_pair.values()
    ):
        raise MultiJudgeAnalysisError("pair/judge population drift")
    return by_pair


def _metric_payload(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {"correct": 0, "n": 0, "agreement": None}
    correct = sum(record["consensus_label"] == record["human_reference"] for record in records)
    ci = bootstrap_percentile([float(record["consensus_label"] == record["human_reference"]) for record in records])
    return {"correct": correct, "n": len(records), "agreement": ci["estimate"], "ci_95": {"low": ci["ci_low"], "high": ci["ci_high"]}}


def _matched_comparator(records: list[dict[str, Any]], judges: tuple[str, ...]) -> dict[str, Any]:
    if not records:
        return {"n": 0, "per_judge": {}, "equal_weight_agreement": None, "delta": None}
    per_judge = {}
    for judge in judges:
        correct = sum(record["votes"][judge] == record["human_reference"] for record in records)
        per_judge[judge] = {"correct": correct, "n": len(records), "agreement": correct / len(records)}
    individual = [sum(record["votes"][judge] == record["human_reference"] for judge in judges) / len(judges) for record in records]
    deltas = [pair_delta(record["consensus_label"], record["human_reference"], [record["votes"][judge] for judge in judges]) for record in records]
    delta_ci = bootstrap_percentile(deltas)
    return {
        "n": len(records), "per_judge": per_judge, "equal_weight_agreement": float(np.mean(individual)),
        "delta": {"estimate": delta_ci["estimate"], "ci_95": {"low": delta_ci["ci_low"], "high": delta_ci["ci_high"]}},
    }


def analyze(session: Session) -> dict[str, Any]:
    protocol, manifest, integrity = _load_frozen_inputs()
    pair_rows = {row["canonical_pair_id"]: row for row in manifest["pairs"]}
    by_pair = _ledger_votes(session, manifest)

    # Structural consensus construction: deliberately no human label is loaded here.
    primary_structural: list[dict[str, Any]] = []
    operational_incomplete = 0
    three_structural: list[dict[str, Any]] = []
    for pair_id, slots in by_pair.items():
        votes = {slot.judge_id: slot.mapped_vote for slot in slots if slot.status == "COMPLETED" and slot.mapped_vote in VALID_VOTES}
        category = pair_rows[pair_id]["category"]
        if len(votes) == 4:
            decision = consensus_for_four(votes[judge] for judge in JUDGES)
            primary_structural.append({"pair_id": pair_id, "category": category, "votes": votes, "pattern": decision.pattern, "consensus_label": decision.label})
        else:
            operational_incomplete += 1
            if len(votes) == 3:
                decision = consensus_for_three(votes.values())
                three_structural.append({"pair_id": pair_id, "category": category, "votes": votes, "pattern": decision.pattern, "consensus_label": decision.label})

    if len(primary_structural) != 1473 or len(three_structural) != 130 or operational_incomplete != 138:
        raise MultiJudgeAnalysisError("frozen structural eligibility counts do not reconcile")
    if any(vote not in VALID_VOTES for record in primary_structural for vote in record["votes"].values()):
        raise MultiJudgeAnalysisError("a non-scientific vote entered the primary analysis")
    patterns = Counter(record["pattern"] for record in primary_structural)
    if sum(patterns.values()) != 1473 or set(patterns) - {"4-0", "3-1", "2-2", "2-1-1"}:
        raise MultiJudgeAnalysisError("primary vote-pattern accounting is invalid")

    # Only now attach human reference labels to preconstructed consensus records.
    labels = _reference_labels(manifest)
    for collection in (primary_structural, three_structural):
        for record in collection:
            record["human_reference"] = labels[record["pair_id"]]

    retained = [record for record in primary_structural if record["consensus_label"] is not None]
    split = [record for record in primary_structural if record["consensus_label"] is None]
    if len(retained) + len(split) + operational_incomplete != 1611:
        raise MultiJudgeAnalysisError("coverage accounting does not reconcile with frozen planned population")

    retained_ids = {record["pair_id"] for record in retained}
    coverage_ci = bootstrap_percentile([float(pair_id in retained_ids) for pair_id in pair_rows])
    primary = _metric_payload(retained)
    comparator = _matched_comparator(retained, JUDGES)
    if comparator["n"] != len(retained):
        raise MultiJudgeAnalysisError("matched comparator population differs from consensus-covered pairs")

    category_results: dict[str, Any] = {}
    for category in sorted({row["category"] for row in manifest["pairs"]}):
        planned = [pair_id for pair_id, row in pair_rows.items() if row["category"] == category]
        structural = [record for record in primary_structural if record["category"] == category]
        category_retained = [record for record in retained if record["category"] == category]
        category_primary = _metric_payload(category_retained)
        category_comparator = _matched_comparator(category_retained, JUDGES)
        category_results[category] = {
            "planned_n": len(planned), "four_valid_n": len(structural), "consensus_covered_n": len(category_retained),
            "consensus_agreement": category_primary["agreement"], "coverage": len(category_retained) / len(planned),
            "equal_weight_individual_agreement": category_comparator["equal_weight_agreement"],
            "consensus_minus_individual_delta": category_comparator["delta"]["estimate"] if category_comparator["delta"] else None,
            "descriptive_only": True,
        }

    sensitivity_retained = [record for record in three_structural if record["consensus_label"] is not None]
    sensitivity_split = [record for record in three_structural if record["consensus_label"] is None]
    sensitivity_primary = _metric_payload(sensitivity_retained)
    sensitivity_judges = tuple(JUDGES)
    # The comparator is pair-specific: only the three observed valid judges participate.
    sensitivity_individual = [sum(vote == record["human_reference"] for vote in record["votes"].values()) / 3 for record in sensitivity_retained]
    sensitivity_deltas = [pair_delta(record["consensus_label"], record["human_reference"], record["votes"].values()) for record in sensitivity_retained]
    sensitivity = {
        "label": "SENSITIVITY_ONLY",
        "eligible_n": len(three_structural), "covered_n": len(sensitivity_retained), "split_n": len(sensitivity_split),
        "agreement": sensitivity_primary["agreement"], "coverage_within_eligible": len(sensitivity_retained) / len(three_structural),
        "coverage_over_planned": len(sensitivity_retained) / 1611,
        "equal_weight_individual_agreement": float(np.mean(sensitivity_individual)) if sensitivity_individual else None,
        "matched_delta": float(np.mean(sensitivity_deltas)) if sensitivity_deltas else None,
        "ci_status": "NOT_PRE_REGISTERED_FOR_SENSITIVITY; PRIMARY_BOOTSTRAP_NOT_REUSED",
        "judges_parameter": sensitivity_judges,
    }

    labels_count = Counter(record["consensus_label"] for record in retained)
    result = {
        "artifact_id": "multi-judge-primary-analysis-v1",
        "phase": "PHASE_8_PRIMARY_MULTI_JUDGE_CONSENSUS_ANALYSIS",
        "protocol": {"id": protocol["protocol_id"], "sha256": EXPECTED_PROTOCOL_SHA256},
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "integrity_artifact": {"path": INTEGRITY_PATH.relative_to(ROOT).as_posix(), "sha256": EXPECTED_INTEGRITY_SHA256, "analysis_ready": True},
        "population": {"planned_pairs": 1611, "planned_slots": 6444, "four_valid_primary_structural_n": len(primary_structural), "three_valid_sensitivity_eligible_n": len(three_structural)},
        "vote_patterns": {
            "4-0": patterns["4-0"], "3-1": patterns["3-1"], "2-2": patterns["2-2"], "2-1-1": patterns["2-1-1"],
            "sum": sum(patterns.values()),
            "rates_among_four_valid": {pattern: count / len(primary_structural) for pattern, count in patterns.items()},
        },
        "primary": {
            "consensus_label_counts": {
                "ORIGINAL_ANSWER_1": labels_count["ORIGINAL_ANSWER_1"], "ORIGINAL_ANSWER_2": labels_count["ORIGINAL_ANSWER_2"],
                "TIE": labels_count["TIE"], "NO_CONSENSUS_SPLIT": len(split),
            },
            "covered_n": len(retained), "coverage": coverage_ci["estimate"], "coverage_ci_95": {"low": coverage_ci["ci_low"], "high": coverage_ci["ci_high"]},
            "split_no_consensus_n": len(split), "operational_no_consensus_n": operational_incomplete, "total_abstention_no_consensus_n": len(split) + operational_incomplete,
            "agreement": primary, "individual_comparator": comparator,
            "consensus_tie_rate_over_planned": labels_count["TIE"] / 1611,
            "consensus_tie_rate_among_covered": labels_count["TIE"] / len(retained),
            "unanimous_share_among_covered": patterns["4-0"] / len(retained),
            "three_of_four_share_among_covered": patterns["3-1"] / len(retained),
        },
        "secondary_operational": {
            "four_valid_structural_coverage": len(primary_structural) / 1611,
            "failure_or_incomplete_rate": operational_incomplete / 1611,
            "split_no_consensus_rate": len(split) / 1611,
            "operational_no_consensus_rate": operational_incomplete / 1611,
            "total_abstention_no_consensus_rate": (len(split) + operational_incomplete) / 1611,
        },
        "per_category": category_results,
        "three_valid_judge_sensitivity": sensitivity,
        "bootstrap": {"unit": "canonical_answer_pair", "method": "nonparametric_percentile", "resamples": BOOTSTRAP_RESAMPLES, "confidence_level": 0.95, "seed": BOOTSTRAP_SEED, "primary_metrics": ["consensus_agreement", "consensus_coverage", "matched_consensus_minus_individual_delta"]},
        "integrity_checks": {
            "no_human_reference_used_for_consensus_construction": True,
            "no_displayed_ab_labels_aggregated": True,
            "no_failed_ambiguous_or_unknown_vote_enters_primary": True,
            "primary_structural_n_matches_phase7": len(primary_structural) == 1473,
            "three_valid_n_matches_phase7": len(three_structural) == 130,
            "retained_comparator_population_equals_covered_population": comparator["n"] == len(retained),
            "no_duplicate_pair": len({record["pair_id"] for record in primary_structural}) == len(primary_structural),
        },
        "interpretation_flags": {
            "human_reference_is_not_ground_truth": True,
            "secondary_category_results_are_descriptive": True,
            "three_valid_result_never_replaces_primary": True,
            "no_dual_swap_comparison": True,
            "no_rq7_promotion": True,
        },
        "provider_activity": {"provider_calls": 0, "spend_usd": "0"},
    }
    return result


def write_analysis(result: dict[str, Any], path: Path = OUTPUT_PATH) -> str:
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return sha256_file(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Provider-free Phase 8 frozen multi-judge analysis")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args(argv)
    with SessionLocal() as session:
        result = analyze(session)
    digest = write_analysis(result, args.output)
    print(f"WROTE {args.output}")
    print(f"SHA256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
