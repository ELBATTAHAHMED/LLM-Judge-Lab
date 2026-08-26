"""Provider-free Phase 9 validation of the frozen matched consensus comparator.

The calculation path reads the immutable manifest/reference dump and durable
execution ledger.  The Phase 8 artifact is used only after recomputation as a
reconciliation target; none of its aggregate values are inputs to a metric.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
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
PHASE8_PATH = ROOT / "evidence" / "multijudge_consensus" / "primary_analysis_v1.json"
OUTPUT_PATH = ROOT / "evidence" / "multijudge_consensus" / "fair_baseline_comparison_v1.json"
PROTOCOL_SHA256 = "819f2e2dea8fb32e4c32000551d6048a16ecc8d28f1bb32d2cce4d02a15c40ce"
MANIFEST_SHA256 = "6c2fa4a926e458c598c73604daa1b69d766bc5b2d04853e73c3a35bf9017e351"
PHASE8_SHA256 = "c881c75b37fc80e4f3ba1e922e1aeba6a28f7125176f6183a38bd48597237693"
JUDGES = (
    "gpt-4o-mini",
    "anthropic/claude-3-haiku",
    "deepseek/deepseek-chat",
    "meta-llama/llama-3.3-70b-instruct",
)
VALID_VOTES = frozenset({"ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_2", "TIE"})
SEED = 20260823
RESAMPLES = 10_000


class FairBaselineValidationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def retained_pair_set_checksum(pair_ids: Iterable[str]) -> str:
    """SHA-256 over the unique canonical IDs in UTF-8 bytewise sorted order."""
    ordered = sorted(pair_ids)
    if len(ordered) != len(set(ordered)):
        raise FairBaselineValidationError("retained pair set contains duplicate canonical IDs")
    return hashlib.sha256("".join(f"{pair_id}\n" for pair_id in ordered).encode("utf-8")).hexdigest()


def frozen_consensus(votes: Iterable[str]) -> str | None:
    """Independent literal implementation of the frozen four-judge rule."""
    values = tuple(votes)
    if len(values) != 4 or any(vote not in VALID_VOTES for vote in values):
        raise FairBaselineValidationError("primary matched set requires four valid scientific votes")
    counts = Counter(values)
    label, count = counts.most_common(1)[0]
    if count >= 3:
        return label
    if len(counts) == 2 or sorted(counts.values()) == [1, 1, 2]:
        return None
    raise FairBaselineValidationError("unrecognised frozen consensus pattern")


def percentile_bootstrap(values: Iterable[float]) -> dict[str, float]:
    array = np.asarray(tuple(values), dtype=float)
    if array.size == 0:
        raise FairBaselineValidationError("cannot bootstrap an empty matched population")
    rng = np.random.default_rng(SEED)
    samples = np.empty(RESAMPLES, dtype=float)
    for index in range(RESAMPLES):
        samples[index] = array[rng.integers(0, array.size, size=array.size)].mean()
    low, high = np.percentile(samples, [2.5, 97.5])
    return {"estimate": float(array.mean()), "ci_95": {"low": float(low), "high": float(high)}}


def _frozen_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    if sha256_file(PROTOCOL_PATH) != PROTOCOL_SHA256:
        raise FairBaselineValidationError("frozen protocol SHA mismatch")
    if sha256_file(MANIFEST_PATH) != MANIFEST_SHA256:
        raise FairBaselineValidationError("frozen manifest SHA mismatch")
    if sha256_file(PHASE8_PATH) != PHASE8_SHA256:
        raise FairBaselineValidationError("frozen Phase 8 analysis SHA mismatch")
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    phase8 = json.loads(PHASE8_PATH.read_text(encoding="utf-8"))
    if protocol.get("protocol_id") != "multi-judge-consensus-v1":
        raise FairBaselineValidationError("unexpected frozen protocol identity")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8")), phase8


def _reference_labels(manifest: dict[str, Any]) -> dict[str, str]:
    grouped: dict[tuple[int, int, int], list[list[str | None]]] = defaultdict(list)
    for row in _copy_rows("human_preferences"):
        grouped[(int(row[1]), *sorted((int(row[2]), int(row[3]))))].append(row)
    labels: dict[str, str] = {}
    for pair in manifest["pairs"]:
        rows = grouped.get((int(pair["prompt_id"]), int(pair["original_answer_1_id"]), int(pair["original_answer_2_id"])), [])
        actual_ids = [int(row[0]) for row in sorted(rows, key=lambda row: int(row[0]))]
        if actual_ids != pair["human_reference_record_ids"]:
            raise FairBaselineValidationError("human reference provenance does not match manifest")
        winners = {row[4] for row in rows}
        if len(winners) != 1:
            raise FairBaselineValidationError("canonical human reference is unavailable")
        winner = next(iter(winners))
        if winner is None:
            labels[pair["canonical_pair_id"]] = "TIE"
        elif int(winner) == int(pair["original_answer_1_id"]):
            labels[pair["canonical_pair_id"]] = "ORIGINAL_ANSWER_1"
        elif int(winner) == int(pair["original_answer_2_id"]):
            labels[pair["canonical_pair_id"]] = "ORIGINAL_ANSWER_2"
        else:
            raise FairBaselineValidationError("reference answer does not belong to canonical pair")
    return labels


def _slots_by_pair(session: Session, manifest: dict[str, Any]) -> dict[str, list[MultiJudgeExecutionSlot]]:
    batch = session.scalar(select(MultiJudgeExecutionBatch).where(MultiJudgeExecutionBatch.manifest_sha256 == MANIFEST_SHA256))
    if batch is None or batch.status != "COMPLETED":
        raise FairBaselineValidationError("completed frozen execution batch is unavailable")
    slots = list(session.scalars(select(MultiJudgeExecutionSlot).where(MultiJudgeExecutionSlot.batch_id == batch.id)))
    if len(slots) != 6444 or len({slot.planned_pass_id for slot in slots}) != 6444:
        raise FairBaselineValidationError("planned slot identity does not reconcile")
    by_pair: dict[str, list[MultiJudgeExecutionSlot]] = defaultdict(list)
    for slot in slots:
        by_pair[slot.canonical_pair_id].append(slot)
    expected = {pair["canonical_pair_id"] for pair in manifest["pairs"]}
    if set(by_pair) != expected or any(len(rows) != 4 or {slot.judge_id for slot in rows} != set(JUDGES) for rows in by_pair.values()):
        raise FairBaselineValidationError("frozen pair/judge population drift")
    return by_pair


def _close(left: Any, right: Any) -> bool:
    return left == right if isinstance(left, int) else abs(float(left) - float(right)) < 1e-12


def validate(session: Session) -> dict[str, Any]:
    manifest, phase8 = _frozen_inputs()
    pair_info = {pair["canonical_pair_id"]: pair for pair in manifest["pairs"]}
    by_pair = _slots_by_pair(session, manifest)

    # Rebuild the retained set before loading human labels or Phase 8 aggregate values.
    four_valid: list[dict[str, Any]] = []
    operational_incomplete = 0
    for pair_id, slots in by_pair.items():
        votes = {slot.judge_id: slot.mapped_vote for slot in slots if slot.status == "COMPLETED" and slot.mapped_vote in VALID_VOTES}
        if len(votes) == 4:
            four_valid.append({"pair_id": pair_id, "votes": votes, "category": pair_info[pair_id]["category"], "consensus_label": frozen_consensus(votes[judge] for judge in JUDGES)})
        else:
            operational_incomplete += 1
    retained = [record for record in four_valid if record["consensus_label"] is not None]
    split = [record for record in four_valid if record["consensus_label"] is None]
    if (len(four_valid), len(retained), len(split), operational_incomplete) != (1473, 1125, 348, 138):
        raise FairBaselineValidationError("independent retention funnel does not reconcile")

    # Reference labels enter only after structural retention is immutable.
    labels = _reference_labels(manifest)
    for record in retained:
        record["human_reference"] = labels[record["pair_id"]]

    consensus_correct = [float(record["consensus_label"] == record["human_reference"]) for record in retained]
    judge_correctness = {
        judge: [float(record["votes"][judge] == record["human_reference"]) for record in retained]
        for judge in JUDGES
    }
    individual_pair_means = [sum(judge_correctness[judge][index] for judge in JUDGES) / 4 for index in range(len(retained))]
    pair_deltas = [consensus_correct[index] - individual_pair_means[index] for index in range(len(retained))]

    consensus = {"correct": int(sum(consensus_correct)), "n": len(retained), "agreement": float(np.mean(consensus_correct))}
    individual = {
        judge: {"correct": int(sum(values)), "n": len(retained), "agreement": float(np.mean(values))}
        for judge, values in judge_correctness.items()
    }
    delta = percentile_bootstrap(pair_deltas)
    categories: dict[str, dict[str, Any]] = {}
    for category in sorted({pair["category"] for pair in manifest["pairs"]}):
        planned_n = sum(pair["category"] == category for pair in manifest["pairs"])
        category_four = [record for record in four_valid if record["category"] == category]
        category_retained = [record for record in retained if record["category"] == category]
        category_individual = [sum(record["votes"][judge] == record["human_reference"] for judge in JUDGES) / 4 for record in category_retained]
        category_consensus = [record["consensus_label"] == record["human_reference"] for record in category_retained]
        categories[category] = {
            "planned_n": planned_n,
            "four_valid_n": len(category_four),
            "consensus_covered_n": len(category_retained),
            "consensus_agreement": float(np.mean(category_consensus)),
            "coverage": len(category_retained) / planned_n,
            "equal_weight_individual_agreement": float(np.mean(category_individual)),
            "consensus_minus_individual_delta": float(np.mean(category_consensus) - np.mean(category_individual)),
            "descriptive_only": True,
        }

    gain_loss = {
        "consensus_correct_individual_mean_below_one": sum(c == 1 and mean < 1 for c, mean in zip(consensus_correct, individual_pair_means)),
        "consensus_incorrect_at_least_one_individual_correct": sum(c == 0 and mean > 0 for c, mean in zip(consensus_correct, individual_pair_means)),
        "all_four_individuals_correct": sum(mean == 1 for mean in individual_pair_means),
        "all_four_individuals_incorrect": sum(mean == 0 for mean in individual_pair_means),
        "positive_effective_correctness_change": sum(change > 0 for change in pair_deltas),
        "negative_effective_correctness_change": sum(change < 0 for change in pair_deltas),
        "no_effective_correctness_change": sum(change == 0 for change in pair_deltas),
    }
    phase8_primary = phase8["primary"]
    expected_individual = phase8_primary["individual_comparator"]
    mismatches: list[str] = []
    checks = {
        "retained_n": (len(retained), phase8_primary["covered_n"]),
        "consensus_correct": (consensus["correct"], phase8_primary["agreement"]["correct"]),
        "consensus_agreement": (consensus["agreement"], phase8_primary["agreement"]["agreement"]),
        "equal_weight_individual_agreement": (float(np.mean(individual_pair_means)), expected_individual["equal_weight_agreement"]),
        "matched_delta": (delta["estimate"], expected_individual["delta"]["estimate"]),
        "delta_ci_low": (delta["ci_95"]["low"], expected_individual["delta"]["ci_95"]["low"]),
        "delta_ci_high": (delta["ci_95"]["high"], expected_individual["delta"]["ci_95"]["high"]),
    }
    for judge in JUDGES:
        checks[f"{judge}_agreement"] = (individual[judge]["agreement"], expected_individual["per_judge"][judge]["agreement"])
        checks[f"{judge}_correct"] = (individual[judge]["correct"], expected_individual["per_judge"][judge]["correct"])
    for name, (actual, expected) in checks.items():
        if not _close(actual, expected):
            mismatches.append(f"{name}: actual={actual!r}, phase8={expected!r}")
    for category, actual in categories.items():
        expected = phase8["per_category"][category]
        for key, value in actual.items():
            if key != "descriptive_only" and not _close(value, expected[key]):
                mismatches.append(f"category {category} {key}: actual={value!r}, phase8={expected[key]!r}")
    if mismatches:
        raise FairBaselineValidationError("Phase 8 reconciliation failed: " + "; ".join(mismatches))

    return {
        "artifact_id": "multi-judge-fair-baseline-comparison-v1",
        "phase": "PHASE_9_FAIR_BASELINE_COMPARISON_VALIDATION",
        "lineage": {"protocol_sha256": PROTOCOL_SHA256, "manifest_sha256": MANIFEST_SHA256, "phase8_artifact_path": PHASE8_PATH.relative_to(ROOT).as_posix(), "phase8_artifact_sha256": PHASE8_SHA256},
        "retained_pair_set": {"n": len(retained), "ordering": "ascending canonical_pair_id Unicode code-point order; UTF-8 newline-delimited", "sha256": retained_pair_set_checksum(record["pair_id"] for record in retained)},
        "independent_recomputation": {
            "consensus": consensus,
            "individual_judges": individual,
            "equal_weight_individual_agreement": float(np.mean(individual_pair_means)),
            "matched_consensus_minus_individual_delta": delta,
        },
        "retention_funnel": {"planned_pairs": 1611, "four_valid_pairs": len(four_valid), "four_valid_rate": len(four_valid) / 1611, "consensus_covered_pairs": len(retained), "consensus_coverage": len(retained) / 1611, "operational_incomplete_pairs": operational_incomplete, "split_no_consensus_pairs": len(split)},
        "pair_level_gain_loss_descriptive": gain_loss,
        "per_judge_consensus_minus_judge_agreement": {judge: consensus["agreement"] - individual[judge]["agreement"] for judge in JUDGES},
        "category_verification": {"status": "PASS", "results": categories, "descriptive_only": True},
        "phase8_reconciliation": {"status": "PASS", "checks": len(checks) + sum(len(result) - 1 for result in categories.values()), "mismatches": []},
        "constraints": {
            "human_reference_is_reference_not_ground_truth": True,
            "matched_comparison_is_conditional_on_consensus_covered_pairs": True,
            "individual_baseline_has_no_separate_comparable_coverage_delta": True,
            "no_dual_swap_comparison": True,
            "no_new_primary_estimand": True,
            "no_rq7_promotion": True,
        },
        "bootstrap": {"unit": "canonical_answer_pair", "method": "nonparametric_percentile", "resamples": RESAMPLES, "confidence_level": 0.95, "seed": SEED, "metric": "matched_consensus_minus_individual_delta"},
        "provider_activity": {"provider_calls": 0, "spend_usd": "0"},
    }


def write_artifact(result: dict[str, Any], path: Path = OUTPUT_PATH) -> str:
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return sha256_file(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Provider-free Phase 9 fair matched baseline validation")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args(argv)
    with SessionLocal() as session:
        result = validate(session)
    digest = write_artifact(result, args.output)
    print(f"WROTE {args.output}")
    print(f"SHA256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
