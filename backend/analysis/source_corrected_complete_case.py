"""Provider-free authoritative analysis of the source-text-corrected lineage.

This module intentionally reads the original controlled ledger only for rows
proved source-correct by the frozen reuse ledger.  Corrected slots replace, but
never supplement, their original logical pass.  Recovery slots replace only
their named failed corrected parent slot.  Nothing in this file performs
provider transport or rewrites an execution outcome.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.multijudge.consensus import EXPECTED_MANIFEST_SHA256 as MULTIJUDGE_MANIFEST_SHA256
from backend.multijudge.consensus import JUDGES as MULTIJUDGE_JUDGES
from backend.multijudge.consensus import VALID_VOTES, _reference_labels, bootstrap_percentile, consensus_for_four, pair_delta
from backend.analysis.metrics import (
    VALID, RQ1Unit, RQ2Repetition, RQ3Pair, RQ7Observation, VariantPair,
    analyze_rq1, analyze_rq2, analyze_rq3, analyze_rq4, analyze_rq5,
    analyze_rq7_matched,
)
from backend.core.controlled_models import AnalysisRun, ControlledRun, Experiment, ExperimentManifest, ExperimentalUnit, RunPass
from backend.evaluation.persistence import to_json_safe
from backend.core.final_evidence import CANONICAL_FINAL_MANIFESTS
from backend.core.final_evidence import CANONICAL_FINAL_ANALYSIS_RUNS
from backend.multijudge.models import MultiJudgeExecutionBatch, MultiJudgeExecutionSlot
from backend.experiments.counterbalanced import (
    ANALYSIS_IDENTITY as RQ6_ANALYSIS_IDENTITY,
    EXPECTED_MANIFEST_SHA256 as RQ6_MANIFEST_SHA256,
    analyze_counterbalanced_observations, load_preflight_manifest,
    reconcile_and_observations,
)
from backend.historical.source_corrected_plan import (
    DATASET_VERSION, MANIFEST_PATH, REUSE_LEDGER_PATH, stable_sha,
)
from backend.historical.source_corrected_models import (
    SourceCorrectedExecutionBatch, SourceCorrectedExecutionSlot,
)
from backend.historical.source_corrected_recovery import RECOVERY_MANIFEST_SHA


ROOT = Path(__file__).resolve().parent.parent.parent
POLICY_IDENTITY = "source-corrected-complete-case-analysis-v1"
ANALYSIS_VERSION = POLICY_IDENTITY
SEED = 20260825
ITERATIONS = 10_000
RECOVERY_MANIFEST_PATH = ROOT / "evidence" / "remediation" / "source_corrected_recovery_manifest_v1.json"
MULTIJUDGE_MANIFEST_PATH = ROOT / "evidence" / "multijudge_consensus" / "execution_manifest_v1.json"
OUTPUT_PATH = ROOT / "evidence" / "remediation" / "source_corrected_complete_case_analysis_v1.json"


class CompleteCaseAnalysisError(RuntimeError):
    pass


@dataclass(frozen=True)
class LogicalPass:
    historical_identity: str
    unit: ExperimentalUnit | None
    rq_code: str
    condition_code: str
    judge_id: str
    presentation: str
    outcome: str | None
    source: str
    canonical_pair_id: str | None = None


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validated_artifacts() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest, ledger = _read_json(MANIFEST_PATH), _read_json(REUSE_LEDGER_PATH)
    recovery, multijudge = _read_json(RECOVERY_MANIFEST_PATH), _read_json(MULTIJUDGE_MANIFEST_PATH)
    if manifest.get("manifest_identity") != "controlled-source-text-corrected-execution-manifest-v1":
        raise CompleteCaseAnalysisError("source-corrected execution manifest identity mismatch")
    if manifest.get("manifest_sha256") != stable_sha({k: v for k, v in manifest.items() if k != "manifest_sha256"}):
        raise CompleteCaseAnalysisError("source-corrected execution manifest SHA mismatch")
    if ledger.get("manifest_sha256") != manifest["manifest_sha256"] or ledger.get("ledger_sha256") != stable_sha({k: v for k, v in ledger.items() if k != "ledger_sha256"}):
        raise CompleteCaseAnalysisError("source-corrected reuse ledger integrity mismatch")
    if recovery.get("recovery_manifest_sha256") != RECOVERY_MANIFEST_SHA:
        raise CompleteCaseAnalysisError("recovery manifest SHA mismatch")
    if len(manifest.get("planned_passes", [])) != 6449 or len(ledger.get("historical_passes", [])) != 24004:
        raise CompleteCaseAnalysisError("frozen corrected execution population mismatch")
    return manifest, ledger, recovery, multijudge


def _presented_to_canonical(outcome: str | None, presentation: str) -> str | None:
    if outcome not in {"ANSWER_A", "ANSWER_B"}:
        return outcome
    if presentation == "AB":
        return outcome
    if presentation == "BA":
        return "ANSWER_B" if outcome == "ANSWER_A" else "ANSWER_A"
    raise CompleteCaseAnalysisError(f"unsupported presentation {presentation!r}")


def _variant_outcome(outcome: str | None, presentation: str) -> str | None:
    if outcome == "TIE":
        return "TIE"
    if outcome not in {"ANSWER_A", "ANSWER_B"}:
        return None
    variant_slot = "B" if presentation == "AB" else "A" if presentation == "BA" else None
    if variant_slot is None:
        raise CompleteCaseAnalysisError(f"unsupported variant presentation {presentation!r}")
    return "VARIANT" if outcome[-1] == variant_slot else "ORIGINAL"


def _controlled_passes(session: Session) -> dict[str, tuple[ExperimentalUnit, RunPass]]:
    rows = list(session.execute(select(ControlledRun, ExperimentalUnit).join(ExperimentalUnit, ControlledRun.experimental_unit_id == ExperimentalUnit.id)))
    result: dict[str, tuple[ExperimentalUnit, RunPass]] = {}
    for run, unit in rows:
        if (run.metadata_json or {}).get("evidence_class") != "CONTROLLED":
            continue
        for pass_ in run.passes:
            identity = f"controlled:{unit.id}:{pass_.pass_number}"
            if identity in result:
                raise CompleteCaseAnalysisError(f"duplicate persisted controlled pass {identity}")
            result[identity] = (unit, pass_)
    return result


def _run_outcome(pass_: RunPass) -> str | None:
    if pass_.outcome:
        return pass_.outcome
    if pass_.raw_verdict in {"ANSWER_A", "ANSWER_B", "TIE", "UNKNOWN"}:
        return pass_.raw_verdict
    return None


def build_logical_view(session: Session) -> tuple[list[LogicalPass], dict[str, Any], dict[str, Any]]:
    manifest, ledger, recovery_manifest, _ = _validated_artifacts()
    parent = session.scalar(select(SourceCorrectedExecutionBatch).where(SourceCorrectedExecutionBatch.manifest_sha256 == manifest["manifest_sha256"]))
    recovery = session.scalar(select(SourceCorrectedExecutionBatch).where(SourceCorrectedExecutionBatch.manifest_sha256 == RECOVERY_MANIFEST_SHA))
    if parent is None or recovery is None or parent.status != "COMPLETED" or recovery.status != "COMPLETED":
        raise CompleteCaseAnalysisError("source-corrected execution batches are not both terminally completed")
    parent_slots = {slot.planned_pass_id: slot for slot in session.scalars(select(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == parent.id))}
    recovery_slots = {slot.original_planned_pass_id: slot for slot in session.scalars(select(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == recovery.id))}
    if len(parent_slots) != 6449 or len(recovery_slots) != 119:
        raise CompleteCaseAnalysisError("durable corrected/recovery slot population mismatch")
    plan_by_id = {row["planned_pass_id"]: row for row in manifest["planned_passes"]}
    recovery_by_original = {row["original_planned_pass_id"]: row for row in recovery_manifest["recovery_slots"]}
    if set(parent_slots) != set(plan_by_id) or set(recovery_slots) != set(recovery_by_original):
        raise CompleteCaseAnalysisError("frozen and durable corrected slot identities differ")
    controlled = _controlled_passes(session)
    units = {str(unit.id): unit for unit in session.scalars(select(ExperimentalUnit))}
    logical: dict[str, LogicalPass] = {}
    reusable = 0
    for row in ledger["historical_passes"]:
        identity = row["historical_pass_identity"]
        if not identity.startswith("controlled:") or row["classification"] != "SOURCE_CORRECT_REUSABLE":
            continue
        persisted = controlled.get(identity)
        if persisted is None:
            raise CompleteCaseAnalysisError(f"reusable controlled pass missing: {identity}")
        unit, pass_ = persisted
        detail = row["details"]
        logical[identity] = LogicalPass(identity, unit, detail["rq_code"], unit.condition_code, unit.judge_model,
                                        detail["exact_identity_checks"]["presentation"], _run_outcome(pass_), "SOURCE_CORRECT_REUSABLE")
        reusable += 1
    replacement_count = 0
    terminal_missing = 0
    for pass_id, planned in plan_by_id.items():
        identity = planned["historical_pass_identity"]
        if not identity.startswith("controlled:"):
            continue
        unit_id = planned["unit_fingerprint"]
        matches = [unit for unit in units.values() if unit.unit_fingerprint == unit_id]
        if len(matches) != 1:
            raise CompleteCaseAnalysisError(f"planned corrected unit fingerprint is not unique: {unit_id}")
        source_slot = parent_slots[pass_id]
        selected, source = source_slot, "CORRECTED_ORIGINAL"
        if source_slot.state != "COMPLETED":
            selected = recovery_slots.get(pass_id)
            source = "RECOVERY_REPLACEMENT"
            if selected is None:
                raise CompleteCaseAnalysisError("failed corrected slot lacks frozen recovery lineage")
        if selected.state != "COMPLETED":
            outcome = None
            terminal_missing += 1
        else:
            outcome = selected.final_outcome
        if identity in logical:
            raise CompleteCaseAnalysisError(f"logical pass double counted: {identity}")
        logical[identity] = LogicalPass(identity, matches[0], planned["rq_code"], planned["condition_code"], planned["judge_id"], planned["presentation"], outcome, source)
        replacement_count += int(source == "RECOVERY_REPLACEMENT")
    expected_controlled = [row["historical_pass_identity"] for row in ledger["historical_passes"] if row["historical_pass_identity"].startswith("controlled:")]
    if set(logical) != set(expected_controlled) or len(logical) != len(expected_controlled):
        raise CompleteCaseAnalysisError("logical controlled view is incomplete or duplicated")
    recovery_completed = sum(slot.state == "COMPLETED" for slot in recovery_slots.values())
    recovery_terminal_missing = sum(slot.state != "COMPLETED" for slot in recovery_slots.values())
    accounting = {
        "logical_controlled_passes": len(logical), "source_correct_reusable_passes": reusable,
        "corrected_original_slots_used": sum(item.source == "CORRECTED_ORIGINAL" for item in logical.values()),
        "recovery_replacements_used_controlled": replacement_count, "terminal_missing_logical_passes_controlled": terminal_missing,
        "recovery_replacements_used_total": recovery_completed, "terminal_missing_logical_passes_total": recovery_terminal_missing,
        "no_double_count": len(logical) == len(set(logical)), "historical_failures_preserved": recovery_terminal_missing == 14,
    }
    return list(logical.values()), accounting, {"manifest": manifest, "recovery_manifest": recovery_manifest}


def _by_rq(rows: Iterable[LogicalPass], rq: str, *, include_reusable: bool = False) -> list[LogicalPass]:
    """Select the frozen corrected-remediation population for a primary RQ.

    The fixed denominators in the protocol are the replacement cohort itself
    (for example 229 RQ1 observations and 243 RQ7 triplets), not every
    historical controlled run that the broad reuse ledger happens to cover.
    ``include_reusable`` is reserved for the superseding full-population
    analysis.  Keeping the original default preserves this provisional
    artifact's historical provenance exactly.
    """
    manifest_rq = "RQ7" if rq.startswith("RQ7") else rq
    expected_manifest = CANONICAL_FINAL_MANIFESTS[manifest_rq]
    return [
        row for row in rows
        if row.rq_code == rq and (include_reusable or row.source != "SOURCE_CORRECT_REUSABLE")
        and row.unit is not None and str(row.unit.manifest_id) == expected_manifest
    ]


def _rq1(rows: list[LogicalPass], *, seed: int = SEED, iterations: int = ITERATIONS) -> dict[str, Any]:
    units = [RQ1Unit("CONTROLLED", row.historical_identity, "RQ1", row.judge_id, row.condition_code,
                     row.unit.human_label if row.unit else None, _presented_to_canonical(row.outcome, row.presentation),
                     row.unit.prompt_category if row.unit else "UNKNOWN") for row in rows]
    return {key: value.serialize() for key, value in analyze_rq1(units, seed=seed, iterations=iterations).items()}


def _rq2(rows: list[LogicalPass], *, seed: int = SEED, iterations: int = ITERATIONS) -> dict[str, Any]:
    values = []
    for row in rows:
        unit = row.unit
        if unit is None:
            raise CompleteCaseAnalysisError("RQ2 logical row has no unit")
        group_key = "|".join((unit.pairing_key or "", row.judge_id, row.condition_code, str(unit.temperature), str(unit.top_p), unit.prompt_template_version))
        values.append(RQ2Repetition("CONTROLLED", row.historical_identity, "RQ2", row.judge_id, row.condition_code,
                                    group_key, unit.answer_a_id, unit.answer_b_id, float(unit.temperature or 0), unit.repetition_index,
                                    0, _presented_to_canonical(row.outcome, row.presentation), unit.provider, unit.provider_model,
                                    unit.prompt_template_version, float(unit.top_p) if unit.top_p is not None else None,
                                    "provider-recorded", row.judge_id, row.route if hasattr(row, "route") else None, None, "controlled-routing-v1", "source-corrected"))
    return {key: value.serialize() for key, value in analyze_rq2(values, seed=seed, iterations=iterations, primary_estimand="strict", include_sensitivity=True, include_by_judge=True).items()}


def _rq3(rows: list[LogicalPass], *, seed: int = SEED, iterations: int = ITERATIONS) -> dict[str, Any]:
    grouped: dict[str, list[LogicalPass]] = defaultdict(list)
    for row in rows:
        grouped[str(row.unit.id)].append(row)
    values = []
    for key, values_for_unit in grouped.items():
        unit = values_for_unit[0].unit
        passes = {row.presentation: _presented_to_canonical(row.outcome, row.presentation) for row in values_for_unit}
        values.append(RQ3Pair("CONTROLLED", key, "RQ3", unit.judge_model, unit.condition_code, passes.get("AB"), passes.get("BA")))
    return {key: value.serialize() for key, value in analyze_rq3(values, seed=seed, iterations=iterations, include_by_judge=True).items()}


def _variant(rows: list[LogicalPass], rq: str, *, seed: int = SEED, iterations: int = ITERATIONS) -> dict[str, Any]:
    grouped: dict[str, list[LogicalPass]] = defaultdict(list)
    for row in rows:
        grouped[str(row.unit.id)].append(row)
    values = []
    for key, pair in grouped.items():
        unit = pair[0].unit
        mapped = [_variant_outcome(row.outcome, row.presentation) for row in pair]
        complete = len(pair) == 2 and mapped[0] in {"VARIANT", "ORIGINAL", "TIE"} and mapped[0] == mapped[1]
        reason = None if complete else "invalid_or_incomplete_pair"
        values.append(VariantPair("CONTROLLED", key, rq, unit.judge_model, unit.condition_code, complete, mapped[0] if complete else None,
                                  unit.presentation_order, bool(unit.counterfactual_variant_id), reason))
    method = analyze_rq4 if rq == "RQ4" else analyze_rq5
    return {key: value.serialize() for key, value in method(values, seed=seed, iterations=iterations, include_exclusion_breakdown=True).items()}


def _rq7_primary(
    rows: list[LogicalPass], *, seed: int = SEED, iterations: int = ITERATIONS,
    expected_complete_case_count: int = 242,
) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[LogicalPass]] = defaultdict(list)
    for row in rows:
        grouped[(row.unit.pairing_key or str(row.unit.id), row.judge_id)].append(row)
    observations = []
    for (pair_key, judge), values in grouped.items():
        human = {row.unit.human_label for row in values}
        if len(human) != 1:
            raise CompleteCaseAnalysisError("RQ7 primary human-label lineage drift")
        baseline = [row for row in values if row.condition_code == "BASELINE_STANDARD"]
        dual = {row.presentation: row for row in values if row.condition_code == "DUAL_SWAP"}
        if len(baseline) != 1 or set(dual) != {"AB", "BA"}:
            raise CompleteCaseAnalysisError("RQ7 primary linked-unit structure drift")
        # A missing physical slot excludes the whole linked unit.  A completed
        # but unstable dual result remains a measured non-covered mitigation.
        if any(row.outcome is None for row in [baseline[0], *dual.values()]):
            continue
        observations.append(RQ7Observation("CONTROLLED", f"{pair_key}:{judge}", "RQ7", judge, "MATCHED", pair_key, human.pop(),
                                            _presented_to_canonical(baseline[0].outcome, baseline[0].presentation),
                                            _presented_to_canonical(dual["AB"].outcome, "AB"),
                                            _presented_to_canonical(dual["BA"].outcome, "BA")))
    if len(observations) != expected_complete_case_count:
        raise CompleteCaseAnalysisError(
            f"RQ7 primary complete-case count expected {expected_complete_case_count}, found {len(observations)}"
        )
    return {key: value.serialize() for key, value in analyze_rq7_matched(observations, seed=seed, iterations=iterations).items()}


def complete_case_populations(logical: list[LogicalPass], *, include_reusable: bool = False) -> dict[str, dict[str, int]]:
    rq1 = _by_rq(logical, "RQ1", include_reusable=include_reusable)
    rq2 = _by_rq(logical, "RQ2", include_reusable=include_reusable)
    rq3 = _by_rq(logical, "RQ3", include_reusable=include_reusable)
    rq4 = _by_rq(logical, "RQ4", include_reusable=include_reusable)
    rq5 = _by_rq(logical, "RQ5", include_reusable=include_reusable)
    rq7 = _by_rq(logical, "RQ7_PRIMARY", include_reusable=include_reusable)
    def groups(rows: list[LogicalPass], key):
        value: dict[Any, list[LogicalPass]] = defaultdict(list)
        for row in rows: value[key(row)].append(row)
        return value
    rq2_groups = groups(rq2, lambda row: (row.unit.pairing_key, row.judge_id, row.condition_code, row.unit.temperature, row.unit.top_p))
    rq3_groups = groups(rq3, lambda row: str(row.unit.id))
    rq4_groups = groups(rq4, lambda row: str(row.unit.id))
    rq5_groups = groups(rq5, lambda row: str(row.unit.id))
    rq7_groups = groups(rq7, lambda row: (row.unit.pairing_key, row.judge_id))
    return {
        "RQ1": {"available_independent_observations": sum(row.outcome is not None for row in rq1), "planned": len(rq1)},
        "RQ2": {"complete_five_repetition_cells": sum(len(group) == 5 and all(row.outcome is not None for row in group) for group in rq2_groups.values()), "planned_cells": len(rq2_groups)},
        "RQ3": {"complete_ab_ba_pairs": sum({row.presentation for row in group} == {"AB", "BA"} and all(row.outcome is not None for row in group) for group in rq3_groups.values()), "planned_pairs": len(rq3_groups)},
        "RQ4": {"complete_matched_pairs": sum(len(group) == 2 and all(row.outcome is not None for row in group) for group in rq4_groups.values()), "planned_pairs": len(rq4_groups)},
        "RQ5": {"complete_matched_pairs": sum(len(group) == 2 and all(row.outcome is not None for row in group) for group in rq5_groups.values()), "planned_pairs": len(rq5_groups)},
        "RQ7_PRIMARY": {"complete_linked_triplets": sum(len(group) == 3 and all(row.outcome is not None for row in group) for group in rq7_groups.values()), "planned_triplets": len(rq7_groups)},
    }


def _rq7_secondary(
    session: Session, manifest: dict[str, Any], *, seed: int = SEED, iterations: int = ITERATIONS,
) -> dict[str, Any]:
    historical_manifest = _read_json(MULTIJUDGE_MANIFEST_PATH)
    pair_rows = {row["canonical_pair_id"]: row for row in historical_manifest["pairs"]}
    batch = session.scalar(select(MultiJudgeExecutionBatch).where(MultiJudgeExecutionBatch.manifest_sha256 == MULTIJUDGE_MANIFEST_SHA256))
    if batch is None or batch.status != "COMPLETED":
        raise CompleteCaseAnalysisError("historical multi-judge batch is unavailable")
    historical = {(slot.canonical_pair_id, slot.judge_id): slot for slot in session.scalars(select(MultiJudgeExecutionSlot).where(MultiJudgeExecutionSlot.batch_id == batch.id))}
    parent = session.scalar(select(SourceCorrectedExecutionBatch).where(SourceCorrectedExecutionBatch.manifest_sha256 == manifest["manifest_sha256"]))
    recovery = session.scalar(select(SourceCorrectedExecutionBatch).where(SourceCorrectedExecutionBatch.manifest_sha256 == RECOVERY_MANIFEST_SHA))
    plan_by_id = {row["planned_pass_id"]: row for row in manifest["planned_passes"] if row["rq_code"] == "RQ7_SECONDARY"}
    parents = {slot.planned_pass_id: slot for slot in session.scalars(select(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == parent.id))}
    replacements = {slot.original_planned_pass_id: slot for slot in session.scalars(select(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == recovery.id))}
    votes: dict[tuple[str, str], str | None] = {}
    returned: dict[tuple[str, str], bool] = {}
    for pair_id in pair_rows:
        for judge in MULTIJUDGE_JUDGES:
            slot = historical[(pair_id, judge)]
            returned[(pair_id, judge)] = slot.status == "COMPLETED"
            votes[(pair_id, judge)] = slot.mapped_vote if slot.status == "COMPLETED" else None
    affected_pairs = {planned["canonical_pair_id"] for planned in plan_by_id.values()}
    if len(affected_pairs) != 498:
        raise CompleteCaseAnalysisError("RQ7 secondary corrected remediation pair count must be 498")
    for pass_id, planned in plan_by_id.items():
        pair_id, judge = planned["canonical_pair_id"], planned["judge_id"]
        slot = parents[pass_id]
        if slot.state != "COMPLETED":
            slot = replacements.get(pass_id)
        outcome = slot.final_outcome if slot is not None and slot.state == "COMPLETED" else None
        returned[(pair_id, judge)] = outcome is not None
        votes[(pair_id, judge)] = (
            "ORIGINAL_ANSWER_1" if _presented_to_canonical(outcome, planned["presentation"]) == "ANSWER_A" else
            "ORIGINAL_ANSWER_2" if _presented_to_canonical(outcome, planned["presentation"]) == "ANSWER_B" else
            "TIE" if outcome == "TIE" else None
        )
    labels = _reference_labels(historical_manifest)
    structural, retained, patterns = [], [], Counter()
    for pair_id in pair_rows:
        pair_votes = {judge: votes[(pair_id, judge)] for judge in MULTIJUDGE_JUDGES}
        if any(value not in VALID_VOTES for value in pair_votes.values()):
            continue
        decision = consensus_for_four(pair_votes[judge] for judge in MULTIJUDGE_JUDGES)
        record = {"pair_id": pair_id, "votes": pair_votes, "pattern": decision.pattern, "consensus_label": decision.label, "human_reference": labels[pair_id]}
        structural.append(record); patterns[decision.pattern] += 1
        if decision.covered:
            retained.append(record)
    remediation_complete = sum(all(returned[(pair_id, judge)] for judge in MULTIJUDGE_JUDGES) for pair_id in affected_pairs)
    remediation_four_valid = sum(all(votes[(pair_id, judge)] in VALID_VOTES for judge in MULTIJUDGE_JUDGES) for pair_id in affected_pairs)
    if remediation_complete != 493:
        raise CompleteCaseAnalysisError(f"RQ7 secondary remediation complete-slot count expected 493, found {remediation_complete}")
    if len(structural) < 1 or len(structural) > len(pair_rows):
        raise CompleteCaseAnalysisError("RQ7 secondary four-vote accounting invalid")
    coverage = bootstrap_percentile([float(any(record["pair_id"] == pair_id for record in retained)) for pair_id in pair_rows], seed=seed, resamples=iterations)
    correct = sum(record["consensus_label"] == record["human_reference"] for record in retained)
    agreement = bootstrap_percentile([float(record["consensus_label"] == record["human_reference"]) for record in retained], seed=seed, resamples=iterations)
    individual = [mean(record["votes"][judge] == record["human_reference"] for judge in MULTIJUDGE_JUDGES) for record in retained]
    deltas = [pair_delta(record["consensus_label"], record["human_reference"], record["votes"].values()) for record in retained]
    delta = bootstrap_percentile(deltas, seed=seed, resamples=iterations)
    per_judge = {judge: sum(record["votes"][judge] == record["human_reference"] for record in retained) / len(retained) for judge in MULTIJUDGE_JUDGES}
    return {
        "planned_n": len(pair_rows), "four_valid_n": len(structural), "consensus_covered_n": len(retained),
        "remediation_subset_planned_n": len(affected_pairs), "remediation_subset_complete_n": remediation_complete,
        "remediation_subset_four_valid_n": remediation_four_valid,
        "coverage": coverage["estimate"], "coverage_ci_95": {"low": coverage["ci_low"], "high": coverage["ci_high"]},
        "agreement": correct / len(retained), "agreement_numerator": correct,
        "agreement_ci_95": {"low": agreement["ci_low"], "high": agreement["ci_high"]},
        "equal_weight_individual_comparator": mean(individual), "matched_delta": delta["estimate"],
        "matched_delta_ci_95": {"low": delta["ci_low"], "high": delta["ci_high"]},
        "vote_pattern_counts": {name: patterns[name] for name in ("4-0", "3-1", "2-2", "2-1-1")},
        "per_judge_retained_pair_agreement": per_judge,
        "strict_rule": "3/4_or_4/4; 2-2 and 2-1-1 are no consensus",
    }


def _metric_row(key: str, value: dict[str, Any]) -> dict[str, Any]:
    return {"metric_key": key, **value}


def _metric_from_payload(result: dict[str, Any], metric_key: str) -> float | None:
    for row in result.get("results", []):
        if row.get("metric_key") == metric_key:
            return row.get("value")
    return None


HISTORICAL_COMPARISON_RUNS: dict[str, str] = {
    "RQ1": "63cd1939-05f4-42cf-a933-4094ac652eea",
    "RQ2": "4013c629-44bf-4021-860b-5c5caba6a8d2",
    "RQ3": "28e45929-c042-4578-be2f-d8f30082b693",
    "RQ4": "057a5a79-0b44-4ba3-9dbb-2d9d01590728",
    "RQ5": "a729804a-5539-400f-998f-83b8c6ada30a",
    "RQ6": "ca2bd7a4-88dc-4be5-883d-cd8f849aa5fa",
    "RQ7": "fa24666d-b4c9-4b1d-a767-cfc59c4380ac",
}


def _historical_comparison(session: Session, results: dict[str, Any]) -> list[dict[str, Any]]:
    """Comparison-only table; pinned historical runs are never analysis input."""
    mapping = {
        "RQ1": ("RQ1", "exact_agreement", "exact_agreement"),
        "RQ2": ("RQ2", "consistency", "consistency"),
        "RQ3": ("RQ3", "paired_decisive_flip_rate", "paired_decisive_flip_rate"),
        "RQ4": ("RQ4", "variant_win_rate", "variant_win_rate"),
        "RQ5": ("RQ5", "variant_win_rate", "variant_win_rate"),
        "RQ6": ("RQ6", "stable_same_family_preference", "stable_same_family_preference"),
        "RQ7_PRIMARY": ("RQ7", "agreement_delta", "agreement_delta"),
    }
    output: list[dict[str, Any]] = []
    for rq_key, (historical_rq, old_key, new_key) in mapping.items():
        row = session.get(AnalysisRun, HISTORICAL_COMPARISON_RUNS[historical_rq])
        if row is None:
            raise CompleteCaseAnalysisError(f"pinned historical AnalysisRun missing for {rq_key}")
        historical = _metric_from_payload(row.result_json or {}, old_key)
        corrected = (results[rq_key].get(new_key) or {}).get("value")
        change = corrected - historical if isinstance(corrected, (int, float)) and isinstance(historical, (int, float)) else None
        output.append({
            "rq": rq_key, "historical_analysis_run_id": str(row.id), "historical_metric": old_key,
            "historical_value": historical, "corrected_value": corrected,
            "absolute_metric_change": abs(change) if change is not None else None,
            "direction_changed": bool(change is not None and historical != 0 and corrected != 0 and (historical > 0) != (corrected > 0)),
            "historical_is_comparison_only": True,
        })
    old_secondary = session.get(AnalysisRun, "fc40faf1-b886-42f8-8faf-a616f61f3107")
    if old_secondary is None:
        raise CompleteCaseAnalysisError("pinned historical multi-judge AnalysisRun missing")
    old_metrics = (old_secondary.result_json or {}).get("metrics", {})
    new_secondary = results["RQ7_SECONDARY"]
    output.append({
        "rq": "RQ7_SECONDARY", "historical_analysis_run_id": str(old_secondary.id),
        "historical_metric": "matched_delta", "historical_value": old_metrics.get("matched_delta"),
        "corrected_value": new_secondary.get("matched_delta"),
        "absolute_metric_change": abs(new_secondary["matched_delta"] - old_metrics["matched_delta"]),
        "direction_changed": (new_secondary["matched_delta"] > 0) != (old_metrics["matched_delta"] > 0),
        "historical_is_comparison_only": True,
    })
    return output


def compute(session: Session) -> dict[str, Any]:
    logical, accounting, artifacts = build_logical_view(session)
    populations = complete_case_populations(logical)
    rq1 = _rq1(_by_rq(logical, "RQ1"))
    rq2 = _rq2(_by_rq(logical, "RQ2"))
    rq3 = _rq3(_by_rq(logical, "RQ3"))
    rq4 = _variant(_by_rq(logical, "RQ4"), "RQ4")
    rq5 = _variant(_by_rq(logical, "RQ5"), "RQ5")
    rq6_manifest = load_preflight_manifest()
    rq6 = {key: value.serialize() for key, value in analyze_counterbalanced_observations(reconcile_and_observations(session, rq6_manifest), seed=SEED, iterations=ITERATIONS).items()}
    rq7_primary = _rq7_primary(_by_rq(logical, "RQ7_PRIMARY"))
    rq7_secondary = _rq7_secondary(session, artifacts["manifest"])
    policy = {
        "identity": POLICY_IDENTITY, "no_imputation": True, "no_model_substitution": True,
        "no_parser_relaxation": True, "additional_provider_calls": 0,
        "linked_unit_rules": {"RQ2": "all five repetitions", "RQ3": "AB and BA", "RQ4": "original and transformed", "RQ7_PRIMARY": "baseline plus both DUAL_SWAP passes", "RQ7_SECONDARY": "four valid judge votes"},
        "missingness": "Claude/OpenRouter/Amazon-Bedrock specific; not proven MCAR or MAR.",
    }
    results = {"RQ1": rq1, "RQ2": rq2, "RQ3": rq3, "RQ4": rq4, "RQ5": rq5, "RQ6": rq6, "RQ7_PRIMARY": rq7_primary, "RQ7_SECONDARY": rq7_secondary}
    result = {
        "artifact_identity": POLICY_IDENTITY,
        "analysis_version": ANALYSIS_VERSION,
        "dataset_version": DATASET_VERSION,
        "policy": policy,
        "lineage": {"corrected_manifest_sha256": artifacts["manifest"]["manifest_sha256"], "recovery_manifest_sha256": RECOVERY_MANIFEST_SHA, "rq6_manifest_sha256": RQ6_MANIFEST_SHA256, "historical_multijudge_manifest_sha256": MULTIJUDGE_MANIFEST_SHA256},
        "logical_observation_accounting": accounting,
        "complete_case_populations": populations,
        "results": results,
        "historical_comparison": _historical_comparison(session, results),
        "missingness_limitation": "Fourteen terminal Claude observations remained unavailable after bounded recovery. Provider response identifiers were retained, but raw rejected response bodies were not persisted, preventing scientifically defensible offline re-parsing. The missing observations are judge-specific and concentrated in a small subset of questions, turns, and categories. Analyses therefore use explicitly reported complete-case populations, without claiming MCAR or MAR.",
        "provider_activity": {"provider_calls": 0, "spend_usd": "0"},
    }
    result["artifact_sha256"] = stable_sha({k: v for k, v in result.items() if k != "artifact_sha256"})
    return result


def _analysis_lineages(session: Session) -> dict[str, tuple[Experiment, ExperimentManifest]]:
    wanted = {"RQ1", "RQ2", "RQ3", "RQ4", "RQ5", "RQ7"}
    rows = list(session.execute(select(Experiment, ExperimentManifest).join(ExperimentManifest).where(ExperimentManifest.rq_code.in_(wanted))))
    picked: dict[str, tuple[Experiment, ExperimentManifest]] = {}
    for experiment, manifest in rows:
        # The frozen phase-4 manifests are the parent lineages for corrected
        # analysis.  A later counterbalanced RQ6 lineage is selected below.
        if manifest.protocol_version == "phase3-controlled-v1" and manifest.rq_code not in picked:
            picked[manifest.rq_code] = (experiment, manifest)
    rq6_rows = list(session.execute(select(Experiment, ExperimentManifest).join(ExperimentManifest).where(ExperimentManifest.manifest_sha256 == RQ6_MANIFEST_SHA256)))
    if len(rq6_rows) != 1 or set(picked) != wanted:
        raise CompleteCaseAnalysisError("parent AnalysisRun lineage is missing or ambiguous")
    picked["RQ6"] = rq6_rows[0]
    return picked


def _run_payload(result: dict[str, Any], rq_key: str) -> dict[str, Any]:
    metrics = result["results"][rq_key]
    return {
        "evidence_class": "CONTROLLED", "dataset_version": DATASET_VERSION,
        "analysis_policy": POLICY_IDENTITY, "artifact_sha256": result["artifact_sha256"],
        "rq_key": rq_key, "metrics": metrics,
        "logical_observation_accounting": result["logical_observation_accounting"],
        "missingness_limitation": result["missingness_limitation"],
        "provider_activity": result["provider_activity"],
    }


def publish(session: Session, result: dict[str, Any]) -> dict[str, str]:
    lineages = _analysis_lineages(session)
    run_ids: dict[str, str] = {}
    for rq_key in ("RQ1", "RQ2", "RQ3", "RQ4", "RQ5", "RQ6", "RQ7_PRIMARY", "RQ7_SECONDARY"):
        base_rq = "RQ7" if rq_key.startswith("RQ7") else rq_key
        experiment, manifest = lineages[base_rq]
        payload = to_json_safe(_run_payload(result, rq_key))
        existing = list(session.scalars(select(AnalysisRun).where(AnalysisRun.manifest_id == manifest.id, AnalysisRun.rq_code == base_rq, AnalysisRun.analysis_version == ANALYSIS_VERSION)).all())
        same = [row for row in existing if (row.result_json or {}).get("rq_key") == rq_key]
        foreign = [row for row in existing if (row.result_json or {}).get("analysis_policy") != POLICY_IDENTITY]
        if len(same) > 1 or foreign:
            raise CompleteCaseAnalysisError(f"ambiguous existing corrected AnalysisRun for {rq_key}")
        if same:
            if same[0].status != "COMPLETED" or same[0].result_json != payload:
                raise CompleteCaseAnalysisError(f"existing corrected AnalysisRun payload drift for {rq_key}")
            row = same[0]
        else:
            row = AnalysisRun(experiment_id=experiment.id, manifest_id=manifest.id, rq_code=base_rq,
                              analysis_version=ANALYSIS_VERSION, analysis_seed=SEED, status="COMPLETED", result_json=payload)
            session.add(row); session.flush()
        run_ids[rq_key] = str(row.id)
    return run_ids


def write_artifact(result: dict[str, Any], run_ids: dict[str, str]) -> None:
    material = {**result, "analysis_run_ids": run_ids}
    OUTPUT_PATH.write_text(json.dumps(material, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_existing(session: Session) -> None:
    """Fast, provider-free integrity check without recomputing bootstrap CIs."""
    _validated_artifacts()
    material = _read_json(OUTPUT_PATH)
    if material.get("artifact_identity") != POLICY_IDENTITY:
        raise CompleteCaseAnalysisError("analysis artifact identity mismatch")
    core = {key: value for key, value in material.items() if key not in {"artifact_sha256", "analysis_run_ids"}}
    if material.get("artifact_sha256") != stable_sha(core):
        raise CompleteCaseAnalysisError("analysis artifact core SHA mismatch")
    expected = material.get("analysis_run_ids") or {}
    if set(expected) != {"RQ1", "RQ2", "RQ3", "RQ4", "RQ5", "RQ6", "RQ7_PRIMARY", "RQ7_SECONDARY"}:
        raise CompleteCaseAnalysisError("analysis artifact does not name exactly eight corrected AnalysisRuns")
    for rq_key, run_id in expected.items():
        row = session.get(AnalysisRun, run_id)
        if row is None or row.status != "COMPLETED" or row.analysis_version != ANALYSIS_VERSION:
            raise CompleteCaseAnalysisError(f"corrected AnalysisRun unavailable: {rq_key}")
        if (row.result_json or {}).get("rq_key") != rq_key or (row.result_json or {}).get("artifact_sha256") != material["artifact_sha256"]:
            raise CompleteCaseAnalysisError(f"corrected AnalysisRun provenance mismatch: {rq_key}")


def main() -> int:
    global ITERATIONS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true", help="persist additive corrected AnalysisRuns")
    parser.add_argument("--verify", action="store_true", help="verify an existing artifact and AnalysisRuns")
    parser.add_argument("--iterations", type=int, default=ITERATIONS, help="bootstrap resamples; defaults to the frozen 10,000")
    parser.add_argument("--summary", action="store_true", help="print compact provider-free accounting instead of all metrics")
    args = parser.parse_args()
    if args.iterations < 1:
        raise CompleteCaseAnalysisError("bootstrap iterations must be positive")
    ITERATIONS = args.iterations
    from backend.core.database import SessionLocal
    with SessionLocal() as session:
        if args.verify:
            verify_existing(session)
            print("SOURCE_CORRECTED_COMPLETE_CASE_ANALYSIS_VERIFIED")
            return 0
        result = compute(session)
        run_ids = publish(session, result) if args.publish else {}
        if args.publish:
            session.commit()
    if args.publish:
        write_artifact(result, run_ids)
    if args.summary:
        print(json.dumps({"artifact_sha256": result["artifact_sha256"], "provider_calls": 0,
                          "accounting": result["logical_observation_accounting"],
                          "primary_metrics": {
                              "rq1": result["results"]["RQ1"]["exact_agreement"],
                              "rq2": result["results"]["RQ2"]["consistency"],
                              "rq3": result["results"]["RQ3"]["paired_decisive_flip_rate"],
                              "rq4": result["results"]["RQ4"]["variant_win_rate"],
                              "rq5": result["results"]["RQ5"]["variant_win_rate"],
                              "rq6": result["results"]["RQ6"]["stable_same_family_preference"],
                              "rq7_primary": result["results"]["RQ7_PRIMARY"]["agreement_delta"],
                              "rq7_secondary": result["results"]["RQ7_SECONDARY"],
                          }}, sort_keys=True))
    else:
        print(json.dumps({"artifact_sha256": result["artifact_sha256"], "provider_calls": 0, "results": result["results"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
