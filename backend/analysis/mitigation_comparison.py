"""Provider-free Phase 10 comparability audit; never invents a DUAL_SWAP collapse."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.analysis.adapter import pass_outcome
from backend.core.controlled_models import AnalysisRun, ControlledRun, Experiment, ExperimentManifest, ExperimentalUnit
from backend.core.database import SessionLocal
from backend.core.final_evidence import CANONICAL_FINAL_ANALYSIS_RUNS, CANONICAL_FINAL_MANIFESTS
from backend.multijudge.models import MultiJudgeExecutionBatch, MultiJudgeExecutionSlot


ROOT = Path(__file__).resolve().parent.parent.parent
MULTI_MANIFEST = ROOT / "evidence" / "multijudge_consensus" / "execution_manifest_v1.json"
PHASE8 = ROOT / "evidence" / "multijudge_consensus" / "primary_analysis_v1.json"
PHASE9 = ROOT / "evidence" / "multijudge_consensus" / "fair_baseline_comparison_v1.json"
OUTPUT = ROOT / "evidence" / "multijudge_consensus" / "dualswap_comparison_v1.json"
PROTOCOL_SHA = "819f2e2dea8fb32e4c32000551d6048a16ecc8d28f1bb32d2cce4d02a15c40ce"
MANIFEST_SHA = "6c2fa4a926e458c598c73604daa1b69d766bc5b2d04853e73c3a35bf9017e351"
PHASE8_SHA = "c881c75b37fc80e4f3ba1e922e1aeba6a28f7125176f6183a38bd48597237693"
PHASE9_SHA = "c362dee20f9d59f9e92ca77f206604b99878c7eaac93247bb346b125ed654bc3"
RQ7_RUN_ID = "fa24666d-b4c9-4b1d-a767-cfc59c4380ac"
RQ7_MANIFEST_ID = "55e58905-2265-49b3-87b7-1d55daa073ea"
JUDGES = ("gpt-4o-mini", "anthropic/claude-3-haiku", "deepseek/deepseek-chat", "meta-llama/llama-3.3-70b-instruct")
VALID_RQ7 = frozenset({"ANSWER_A", "ANSWER_B", "TIE"})
VALID_MULTI = frozenset({"ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_2", "TIE"})


class ComparisonError(RuntimeError):
    pass


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def set_digest(keys: Iterable[str]) -> str:
    ordered = sorted(keys)
    if len(ordered) != len(set(ordered)):
        raise ComparisonError("duplicate identity in deterministic set")
    return hashlib.sha256("".join(f"{key}\n" for key in ordered).encode()).hexdigest()


def key(dataset_id: str, prompt_id: int, answer_a: int, answer_b: int) -> str:
    return json.dumps([dataset_id, prompt_id, min(answer_a, answer_b), max(answer_a, answer_b)], separators=(",", ":"))


def multi_consensus(votes: Iterable[str]) -> str | None:
    values = tuple(votes)
    if len(values) != 4 or any(vote not in VALID_MULTI for vote in values):
        raise ComparisonError("invalid multi-judge vote set")
    label, count = Counter(values).most_common(1)[0]
    return label if count >= 3 else None


def bootstrap(values: list[int], *, seed: int = 20260818, iterations: int = 10_000) -> tuple[float, float]:
    rng = random.Random(seed)
    samples = []
    for _ in range(iterations):
        samples.append(mean(values[rng.randrange(len(values))] for _ in values))
    samples.sort()
    return samples[int(.025 * (len(samples) - 1))], samples[int(.975 * (len(samples) - 1))]


def mapped(run_pass: Any, unit: ExperimentalUnit) -> str | None:
    value = pass_outcome(run_pass)
    if value not in {"ANSWER_A", "ANSWER_B"}:
        return value
    if run_pass.winner_answer_id == unit.answer_a_id:
        return "ANSWER_A"
    if run_pass.winner_answer_id == unit.answer_b_id:
        return "ANSWER_B"
    return "INVALID_RESPONSE"


def _metric_map(run: AnalysisRun) -> dict[str, dict[str, Any]]:
    return {row["metric_key"]: row for row in run.result_json["results"]}


def _close(left: float, right: float) -> bool:
    return abs(left - right) < 1e-12


def analyze(session: Session) -> dict[str, Any]:
    if (digest(MULTI_MANIFEST), digest(PHASE8), digest(PHASE9)) != (MANIFEST_SHA, PHASE8_SHA, PHASE9_SHA):
        raise ComparisonError("frozen multi-judge lineage checksum mismatch")
    manifest = json.loads(MULTI_MANIFEST.read_text(encoding="utf-8"))
    rq7 = session.get(AnalysisRun, uuid.UUID(RQ7_RUN_ID))
    if rq7 is None or str(rq7.manifest_id) != RQ7_MANIFEST_ID or rq7.status != "COMPLETED":
        raise ComparisonError("authoritative current RQ7 AnalysisRun is unavailable")
    if CANONICAL_FINAL_ANALYSIS_RUNS["RQ7"] != RQ7_RUN_ID or CANONICAL_FINAL_MANIFESTS["RQ7"] != RQ7_MANIFEST_ID:
        raise ComparisonError("RQ7 current-release pin differs from required lineage")
    rq7_manifest = session.get(ExperimentManifest, rq7.manifest_id)
    experiment = session.get(Experiment, rq7.experiment_id)
    if rq7_manifest is None or experiment is None or str(rq7_manifest.experiment_id) != str(experiment.id):
        raise ComparisonError("RQ7 manifest provenance is invalid")
    dataset_id = str(experiment.dataset_version_id)
    if dataset_id != manifest["dataset"]["dataset_version_id"]:
        raise ComparisonError("dataset/source identities differ")

    units = list(session.scalars(select(ExperimentalUnit).where(ExperimentalUnit.manifest_id == rq7.manifest_id)))
    runs = list(session.scalars(select(ControlledRun).where(ControlledRun.experimental_unit_id.in_([unit.id for unit in units]))))
    controlled = [run for run in runs if (run.metadata_json or {}).get("evidence_class") == "CONTROLLED"]
    by_unit = {run.experimental_unit_id: run for run in controlled}
    if len(units) != 1600 or len(by_unit) != len(units):
        raise ComparisonError("RQ7 controlled run/unit population does not reconcile")

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for unit in units:
        run = by_unit[unit.id]
        identity = key(dataset_id, unit.prompt_id, unit.answer_a_id, unit.answer_b_id)
        group = grouped.setdefault((unit.pairing_key or str(unit.id), run.judge_name), {"canonical_key": identity, "category": unit.prompt_category, "human": unit.human_label})
        if group["canonical_key"] != identity or group["human"] != unit.human_label:
            raise ComparisonError("RQ7 pairing key does not preserve immutable pair provenance")
        values = [mapped(record, unit) for record in sorted(run.passes, key=lambda record: record.pass_number)]
        if unit.condition_code == "BASELINE_STANDARD":
            group["baseline"] = values[0] if values else None
        elif unit.condition_code == "DUAL_SWAP":
            group["dual"] = values[0] if len(values) == 2 and values[0] == values[1] and values[0] in VALID_RQ7 else None
        else:
            raise ComparisonError("unexpected RQ7 condition")
    observations = list(grouped.values())
    if len(observations) != 800 or any("baseline" not in row or "dual" not in row for row in observations):
        raise ComparisonError("RQ7 unit is not one matched pair-by-judge observation")

    baseline_valid = [row for row in observations if row["baseline"] in VALID_RQ7]
    dual_valid = [row for row in observations if row["dual"] in VALID_RQ7]
    retained = [row for row in observations if row["human"] in VALID_RQ7 and row["baseline"] in VALID_RQ7 and row["dual"] in VALID_RQ7]
    baseline_correct = [int(row["baseline"] == row["human"]) for row in retained]
    dual_correct = [int(row["dual"] == row["human"]) for row in retained]
    deltas = [right - left for left, right in zip(baseline_correct, dual_correct)]
    low, high = bootstrap(deltas)
    computed = {
        "baseline_coverage": len(baseline_valid) / len(observations), "dual_swap_coverage": len(dual_valid) / len(observations),
        "coverage_delta": len(dual_valid) / len(observations) - len(baseline_valid) / len(observations),
        "baseline_agreement": mean(baseline_correct), "dual_swap_agreement": mean(dual_correct),
        "agreement_delta": mean(deltas), "agreement_delta_ci_low": low, "agreement_delta_ci_high": high,
        "matched_n": len(retained), "planned_pair_by_judge_n": len(observations),
    }
    stored = _metric_map(rq7)
    stored_expected = {
        "baseline_coverage": stored["baseline_coverage"]["value"], "dual_swap_coverage": stored["dual_swap_coverage"]["value"],
        "coverage_delta": stored["coverage_delta"]["value"], "baseline_agreement": stored["baseline_agreement"]["value"],
        "dual_swap_agreement": stored["dual_swap_agreement"]["value"], "agreement_delta": stored["agreement_delta"]["value"],
        "agreement_delta_ci_low": stored["agreement_delta"]["ci_low"], "agreement_delta_ci_high": stored["agreement_delta"]["ci_high"],
        "matched_n": stored["agreement_delta"]["analyzed_n"],
    }
    mismatch = [name for name, expected in stored_expected.items() if not _close(float(computed[name]), float(expected))]
    if mismatch:
        raise ComparisonError("current RQ7 raw reconstruction mismatch: " + ", ".join(mismatch))

    batch = session.scalar(select(MultiJudgeExecutionBatch).where(MultiJudgeExecutionBatch.manifest_sha256 == MANIFEST_SHA))
    slots = list(session.scalars(select(MultiJudgeExecutionSlot).where(MultiJudgeExecutionSlot.batch_id == batch.id))) if batch else []
    multi_by_pair: dict[str, list[MultiJudgeExecutionSlot]] = defaultdict(list)
    for slot in slots:
        multi_by_pair[slot.canonical_pair_id].append(slot)
    manifest_pairs = {pair["canonical_pair_id"]: pair for pair in manifest["pairs"]}
    if len(manifest_pairs) != 1611 or set(multi_by_pair) != set(manifest_pairs):
        raise ComparisonError("multi-judge pair ledger mismatch")
    multi_covered_keys = set()
    for pair_id, pair in manifest_pairs.items():
        votes = [slot.mapped_vote for slot in multi_by_pair[pair_id] if slot.status == "COMPLETED" and slot.mapped_vote in VALID_MULTI]
        if len(votes) == 4 and multi_consensus(votes) is not None:
            multi_covered_keys.add(key(str(manifest["dataset"]["dataset_version_id"]), pair["prompt_id"], pair["original_answer_1_id"], pair["original_answer_2_id"]))
    multi_planned_keys = {key(dataset_id, pair["prompt_id"], pair["original_answer_1_id"], pair["original_answer_2_id"]) for pair in manifest_pairs.values()}
    dual_keys = {row["canonical_key"] for row in observations}
    overlap = dual_keys & multi_planned_keys
    retained_crosswalk_rows = [row for row in retained if row["canonical_key"] in multi_covered_keys]
    overlap_categories = Counter(row["category"] for row in observations if row["canonical_key"] in overlap)
    decision = "DIRECT_MATCHED_COMPARISON_NOT_DEFENSIBLE"
    return {
        "artifact_id": "dualswap-vs-multijudge-comparison-v1", "phase": "PHASE_10_FAIR_COMPARISON",
        "lineage": {"protocol_sha256": PROTOCOL_SHA, "manifest_sha256": MANIFEST_SHA, "phase8_sha256": PHASE8_SHA, "phase9_sha256": PHASE9_SHA, "rq7_analysis_run_id": RQ7_RUN_ID, "rq7_manifest_id": RQ7_MANIFEST_ID, "rq7_analysis_seed": rq7.analysis_seed},
        "dual_swap_unit": {"unit": "canonical answer pair × judge", "planned_n": len(observations), "unique_canonical_pairs": len(dual_keys), "judge_models": sorted({judge for _, judge in grouped}), "frozen_pair_level_aggregation_rule": None},
        "multi_judge_unit": {"unit": "canonical answer pair", "planned_n": len(multi_planned_keys), "consensus_covered_n": len(multi_covered_keys)},
        "rq7_independent_reconstruction": computed,
        "exact_identity_overlap": {"dual_swap_canonical_pairs": len(dual_keys), "multi_judge_planned_pairs": len(multi_planned_keys), "overlap_n": len(overlap), "overlap_sha256": set_digest(overlap), "multi_judge_covered_within_overlap_n": len(overlap & multi_covered_keys), "multi_judge_covered_within_overlap_sha256": set_digest(overlap & multi_covered_keys), "dual_swap_retained_pair_by_judge_rows_on_multi_covered_pairs": len(retained_crosswalk_rows), "both_method_retained_common_n": None, "both_method_retained_common_n_status": "NOT_DEFINED_NO_FROZEN_PAIR_LEVEL_DUAL_SWAP_AGGREGATION"},
        "unit_compatibility": {"status": "FAIL", "reason": "DUAL_SWAP has repeated pair×judge observations (800 rows over 653 canonical pairs); Multi-Judge has one canonical-pair decision. No frozen RQ7 method aggregates the repeated DUAL_SWAP judge observations to a pair-level outcome."},
        "direct_comparison": {"decision": decision, "direct_delta": None, "bootstrap_ci_95": None, "matched_n": None, "coverage_comparison": "NOT_COMPARABLE_AS_MATCHED_DELTA"},
        "separate_operating_points": {"dual_swap": computed, "multi_judge": {"planned_n": 1611, "covered_n": 1125, "coverage": 1125 / 1611, "agreement": 795 / 1125, "equal_weight_individual_baseline": 0.658, "matched_delta": 0.048666666666666664}},
        "baseline_composition_diagnostic": {"status": "DESCRIPTIVE_ONLY", "all_dual_swap_canonical_pairs_are_in_multi_judge_planned_population": len(overlap) == len(dual_keys), "dual_swap_pair_by_judge_repetition_prevents_pair_level_direct_baseline_normalization": True},
        "category_comparability": {"status": "DESCRIPTIVE_ONLY", "shared_canonical_pair_category_counts_from_dual_swap_observations": dict(sorted(overlap_categories.items())), "no_per_category_direct_effect_computed": True},
        "historical_unmatched_plus_8_13_pp_used_as_primary": False,
        "constraints": {"no_rq7_modification": True, "no_api_frontend_modification": True, "no_phase11_or_release_modification": True, "no_judge_aggregation_invented": True, "no_superiority_claim": True},
        "provider_activity": {"provider_calls": 0, "spend_usd": "0"},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Provider-free Phase 10 dual-swap comparability audit")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    with SessionLocal() as session:
        result = analyze(session)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"WROTE {args.output}")
    print(f"SHA256 {digest(args.output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
