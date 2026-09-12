"""Question-clustered bootstrap sensitivity analysis for the frozen study.

This module is additive validation tooling. It never writes the database,
changes an AnalysisRun, or replaces an official confidence interval.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Callable, Iterable, Mapping, Sequence, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.analysis.metrics import VALID
from backend.analysis.source_corrected_complete_case import (
    MULTIJUDGE_JUDGES,
    MULTIJUDGE_MANIFEST_PATH,
    MULTIJUDGE_MANIFEST_SHA256,
    RECOVERY_MANIFEST_SHA,
    _by_rq,
    _presented_to_canonical,
    _read_json,
    _reference_labels,
    _variant_outcome,
    build_logical_view,
)
from backend.core.models import Prompt
from backend.data.canonical import load_raw_source
from backend.experiments.counterbalanced import load_preflight_manifest, reconcile_and_observations
from backend.historical.source_corrected_models import SourceCorrectedExecutionBatch, SourceCorrectedExecutionSlot
from backend.multijudge.consensus import consensus_for_four, pair_delta
from backend.multijudge.models import MultiJudgeExecutionBatch, MultiJudgeExecutionSlot


ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_ARTIFACT = ROOT / "evidence" / "remediation" / "source_corrected_complete_case_full_population_analysis_v2.json"
OUTPUT_JSON = ROOT / "evidence" / "validation" / "question_clustered_bootstrap_sensitivity_v1.json"
OUTPUT_REPORT = ROOT / "evidence" / "validation" / "question_clustered_bootstrap_sensitivity_v1.md"
ANALYSIS_ID = "question-clustered-bootstrap-sensitivity-v1"
SEED = 20260912
RESAMPLES = 10_000
SECONDARY_VALID = frozenset({"ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_2", "TIE"})
T = TypeVar("T")


class ClusteredBootstrapError(RuntimeError):
    pass


@dataclass(frozen=True)
class ClusteredBootstrapResult:
    ci_low: float | None
    ci_high: float | None
    question_clusters: int
    bootstrap_replicates: int
    valid_replicates: int
    non_estimable_replicates: int


def question_clustered_bootstrap(
    observations: Sequence[T],
    *,
    question_id: Callable[[T], int],
    statistic: Callable[[Sequence[T]], float | None],
    seed: int = SEED,
    resamples: int = RESAMPLES,
) -> ClusteredBootstrapResult:
    """Resample question IDs and retain every observation in each sampled cluster."""
    grouped: dict[int, list[T]] = defaultdict(list)
    for observation in observations:
        grouped[int(question_id(observation))].append(observation)
    cluster_ids = sorted(grouped)
    if not cluster_ids or resamples < 1:
        return ClusteredBootstrapResult(None, None, len(cluster_ids), resamples, 0, resamples)
    rng = random.Random(seed)
    estimates: list[float] = []
    non_estimable = 0
    for _ in range(resamples):
        sample: list[T] = []
        for _ in cluster_ids:
            sampled_id = cluster_ids[rng.randrange(len(cluster_ids))]
            sample.extend(grouped[sampled_id])
        value = statistic(sample)
        if value is None or not math.isfinite(value):
            non_estimable += 1
        else:
            estimates.append(float(value))
    if not estimates:
        return ClusteredBootstrapResult(None, None, len(cluster_ids), resamples, 0, non_estimable)
    estimates.sort()
    low = estimates[int(0.025 * (len(estimates) - 1))]
    high = estimates[int(0.975 * (len(estimates) - 1))]
    return ClusteredBootstrapResult(low, high, len(cluster_ids), resamples, len(estimates), non_estimable)


def _safe_mean(values: Iterable[float]) -> float | None:
    rows = list(values)
    return mean(rows) if rows else None


def _rate(rows: Sequence[dict[str, Any]], predicate: Callable[[dict[str, Any]], bool]) -> float | None:
    return sum(predicate(row) for row in rows) / len(rows) if rows else None


def _rq1_valid(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row["human"] in VALID and row["judge"] in VALID]


def _rq1_agreement(rows: Sequence[dict[str, Any]]) -> float | None:
    return _rate(_rq1_valid(rows), lambda row: row["human"] == row["judge"])


def _rq1_kappa(rows: Sequence[dict[str, Any]]) -> float | None:
    valid = _rq1_valid(rows)
    if not valid:
        return None
    classes = ("ANSWER_A", "ANSWER_B", "TIE")
    observed = sum(row["human"] == row["judge"] for row in valid) / len(valid)
    human = Counter(row["human"] for row in valid)
    judge = Counter(row["judge"] for row in valid)
    expected = sum(human[label] * judge[label] for label in classes) / len(valid) ** 2
    return None if expected == 1 else (observed - expected) / (1 - expected)


def _rq3_flip(rows: Sequence[dict[str, Any]]) -> float | None:
    decisive = [row for row in rows if row["ab"] in {"ANSWER_A", "ANSWER_B"} and row["ba"] in {"ANSWER_A", "ANSWER_B"}]
    return _rate(decisive, lambda row: row["ab"] != row["ba"])


def _variant_rate(rows: Sequence[dict[str, Any]]) -> float | None:
    valid = [row for row in rows if row["valid"] and row["outcome"] in {"VARIANT", "ORIGINAL", "TIE"}]
    return _rate(valid, lambda row: row["outcome"] == "VARIANT")


def _rq6_rate(rows: Sequence[dict[str, Any]]) -> float | None:
    stable = [row for row in rows if row["stable"] in {"SAME", "OTHER"}]
    return _rate(stable, lambda row: row["stable"] == "SAME")


def _dual_label(row: Mapping[str, Any]) -> str | None:
    return row["dual_ab"] if row["dual_ab"] == row["dual_ba"] and row["dual_ab"] in VALID else None


def _rq7_primary_delta(rows: Sequence[dict[str, Any]]) -> float | None:
    matched = [row for row in rows if row["human"] in VALID and row["baseline"] in VALID and _dual_label(row) in VALID]
    return _safe_mean(int(_dual_label(row) == row["human"]) - int(row["baseline"] == row["human"]) for row in matched)


def _rq7_primary_coverage_delta(rows: Sequence[dict[str, Any]]) -> float | None:
    return _safe_mean(int(_dual_label(row) in VALID) - int(row["baseline"] in VALID) for row in rows)


def _secondary_retained(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row["consensus"] in SECONDARY_VALID]


def _secondary_agreement(rows: Sequence[dict[str, Any]]) -> float | None:
    return _rate(_secondary_retained(rows), lambda row: row["consensus"] == row["human"])


def _secondary_coverage(rows: Sequence[dict[str, Any]]) -> float | None:
    return _rate(list(rows), lambda row: row["consensus"] in SECONDARY_VALID)


def _secondary_delta(rows: Sequence[dict[str, Any]]) -> float | None:
    retained = _secondary_retained(rows)
    return _safe_mean(pair_delta(row["consensus"], row["human"], row["votes"].values()) for row in retained)


def _prompt_question_map(session: Session, prompt_ids: set[int]) -> dict[int, int]:
    source = load_raw_source()
    source_by_text: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for source_key, text in source.prompts.items():
        source_by_text[text].append(source_key)
    prompts = {row.id: row.text for row in session.scalars(select(Prompt).where(Prompt.id.in_(prompt_ids)))}
    if set(prompts) != prompt_ids:
        raise ClusteredBootstrapError("a controlled prompt ID is missing from the database")
    mapped: dict[int, int] = {}
    for prompt_id, text in prompts.items():
        candidates = source_by_text.get(text, [])
        if len(candidates) != 1:
            raise ClusteredBootstrapError(f"prompt {prompt_id} does not map uniquely to an original MT-Bench question")
        mapped[prompt_id] = int(candidates[0][0])
    return mapped


def _controlled_observations(session: Session) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    logical, accounting, artifacts = build_logical_view(session)
    prompt_ids = {row.unit.prompt_id for row in logical if row.unit is not None}
    question_by_prompt = _prompt_question_map(session, prompt_ids)
    output: dict[str, list[dict[str, Any]]] = {}

    rq1 = []
    for row in _by_rq(logical, "RQ1", include_reusable=True):
        rq1.append({"question_id": question_by_prompt[row.unit.prompt_id], "human": row.unit.human_label, "judge": _presented_to_canonical(row.outcome, row.presentation)})
    output["RQ1"] = rq1

    rq2_groups: dict[str, list[Any]] = defaultdict(list)
    for row in _by_rq(logical, "RQ2", include_reusable=True):
        unit = row.unit
        key = "|".join((unit.pairing_key or "", row.judge_id, row.condition_code, str(unit.temperature), str(unit.top_p), unit.prompt_template_version))
        rq2_groups[key].append(row)
    rq2 = []
    for rows in rq2_groups.values():
        unit = rows[0].unit
        labels = [_presented_to_canonical(row.outcome, row.presentation) for row in rows]
        repetitions = {row.unit.repetition_index for row in rows}
        complete = len(rows) == 5 and len(repetitions) == 5
        valid = [label for label in labels if label in VALID]
        rq2.append({
            "question_id": question_by_prompt[unit.prompt_id],
            "strict": max(Counter(valid).values()) / len(valid) if complete and len(valid) == 5 else None,
            "conditional": max(Counter(valid).values()) / len(valid) if complete and valid else None,
        })
    output["RQ2"] = rq2

    for rq in ("RQ3", "RQ4", "RQ5"):
        grouped: dict[str, list[Any]] = defaultdict(list)
        for row in _by_rq(logical, rq, include_reusable=True):
            grouped[str(row.unit.id)].append(row)
        records: list[dict[str, Any]] = []
        for rows in grouped.values():
            unit = rows[0].unit
            if rq == "RQ3":
                presentations = {row.presentation: _presented_to_canonical(row.outcome, row.presentation) for row in rows}
                records.append({"question_id": question_by_prompt[unit.prompt_id], "ab": presentations.get("AB"), "ba": presentations.get("BA")})
            else:
                mapped = [_variant_outcome(row.outcome, row.presentation) for row in rows]
                valid = len(rows) == 2 and mapped[0] in {"VARIANT", "ORIGINAL", "TIE"} and mapped[0] == mapped[1]
                records.append({"question_id": question_by_prompt[unit.prompt_id], "valid": valid, "outcome": mapped[0] if valid else None})
        output[rq] = records

    rq7_groups: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for row in _by_rq(logical, "RQ7_PRIMARY", include_reusable=True):
        rq7_groups[(row.unit.pairing_key or str(row.unit.id), row.judge_id)].append(row)
    rq7 = []
    for rows in rq7_groups.values():
        baseline = [row for row in rows if row.condition_code == "BASELINE_STANDARD"]
        dual = {row.presentation: row for row in rows if row.condition_code == "DUAL_SWAP"}
        if len(baseline) != 1 or set(dual) != {"AB", "BA"}:
            raise ClusteredBootstrapError("RQ7 primary linked-unit structure drift")
        if any(row.outcome is None for row in [baseline[0], *dual.values()]):
            continue
        unit = rows[0].unit
        rq7.append({
            "question_id": question_by_prompt[unit.prompt_id],
            "human": unit.human_label,
            "baseline": _presented_to_canonical(baseline[0].outcome, baseline[0].presentation),
            "dual_ab": _presented_to_canonical(dual["AB"].outcome, "AB"),
            "dual_ba": _presented_to_canonical(dual["BA"].outcome, "BA"),
        })
    output["RQ7_PRIMARY"] = rq7
    return output, {"logical_accounting": accounting, "corrected_manifest": artifacts["manifest"]}


def _rq6_observations(session: Session) -> list[dict[str, Any]]:
    manifest = load_preflight_manifest()
    specs = {row["unit_id"]: row for row in manifest["units"]}
    observations = reconcile_and_observations(session, manifest)
    rows = [{"question_id": int(specs[row.unit_id]["prompt_id"]), "stable": row.stable} for row in observations]
    if not all(81 <= row["question_id"] <= 160 for row in rows):
        raise ClusteredBootstrapError("RQ6 manifest prompt identity is outside the MT-Bench question range")
    return rows


def _secondary_observations(session: Session, corrected_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    historical_manifest = _read_json(MULTIJUDGE_MANIFEST_PATH)
    pair_rows = {row["canonical_pair_id"]: row for row in historical_manifest["pairs"]}
    batch = session.scalar(select(MultiJudgeExecutionBatch).where(MultiJudgeExecutionBatch.manifest_sha256 == MULTIJUDGE_MANIFEST_SHA256))
    if batch is None or batch.status != "COMPLETED":
        raise ClusteredBootstrapError("completed Multi-Judge batch is unavailable")
    historical = {(slot.canonical_pair_id, slot.judge_id): slot for slot in session.scalars(select(MultiJudgeExecutionSlot).where(MultiJudgeExecutionSlot.batch_id == batch.id))}
    parent = session.scalar(select(SourceCorrectedExecutionBatch).where(SourceCorrectedExecutionBatch.manifest_sha256 == corrected_manifest["manifest_sha256"]))
    recovery = session.scalar(select(SourceCorrectedExecutionBatch).where(SourceCorrectedExecutionBatch.manifest_sha256 == RECOVERY_MANIFEST_SHA))
    if parent is None or recovery is None:
        raise ClusteredBootstrapError("source-corrected Multi-Judge lineage is unavailable")
    plan_by_id = {row["planned_pass_id"]: row for row in corrected_manifest["planned_passes"] if row["rq_code"] == "RQ7_SECONDARY"}
    parents = {slot.planned_pass_id: slot for slot in session.scalars(select(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == parent.id))}
    replacements = {slot.original_planned_pass_id: slot for slot in session.scalars(select(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == recovery.id))}
    votes: dict[tuple[str, str], str | None] = {}
    for pair_id in pair_rows:
        for judge in MULTIJUDGE_JUDGES:
            slot = historical[(pair_id, judge)]
            votes[(pair_id, judge)] = slot.mapped_vote if slot.status == "COMPLETED" else None
    for pass_id, planned in plan_by_id.items():
        pair_id, judge = planned["canonical_pair_id"], planned["judge_id"]
        slot = parents[pass_id]
        if slot.state != "COMPLETED":
            slot = replacements.get(pass_id)
        outcome = slot.final_outcome if slot is not None and slot.state == "COMPLETED" else None
        mapped = _presented_to_canonical(outcome, planned["presentation"])
        votes[(pair_id, judge)] = "ORIGINAL_ANSWER_1" if mapped == "ANSWER_A" else "ORIGINAL_ANSWER_2" if mapped == "ANSWER_B" else "TIE" if mapped == "TIE" else None
    labels = _reference_labels(historical_manifest)
    records = []
    for pair_id, pair in pair_rows.items():
        pair_votes = {judge: votes[(pair_id, judge)] for judge in MULTIJUDGE_JUDGES}
        consensus = None
        if all(value in {"ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_2", "TIE"} for value in pair_votes.values()):
            consensus = consensus_for_four(pair_votes[judge] for judge in MULTIJUDGE_JUDGES).label
        records.append({"question_id": int(pair["prompt_id"]), "human": labels[pair_id], "votes": pair_votes, "consensus": consensus})
    if sorted({row["question_id"] for row in records}) != list(range(81, 161)):
        raise ClusteredBootstrapError("Multi-Judge manifest does not cover the 80 original MT-Bench questions")
    return records


def _official_ci(metric: dict[str, Any]) -> tuple[float | None, float | None]:
    return metric.get("ci_low"), metric.get("ci_high")


def _contains(ci: tuple[float | None, float | None], null: float | None) -> bool | None:
    return None if null is None or ci[0] is None or ci[1] is None else bool(ci[0] <= null <= ci[1])


def _comparison(
    *,
    metric_id: str,
    role: str,
    rows: list[dict[str, Any]],
    statistic: Callable[[Sequence[dict[str, Any]]], float | None],
    official_point: float,
    official_ci: tuple[float | None, float | None],
    official_method: str,
    official_unit: str,
    observation_denominator: int,
    null_value: float | None,
    notes: str,
) -> dict[str, Any]:
    point = statistic(rows)
    if point is None or not math.isclose(point, official_point, rel_tol=0, abs_tol=1e-12):
        raise ClusteredBootstrapError(f"{metric_id} point estimate does not reproduce official evidence: {point!r} != {official_point!r}")
    clustered = question_clustered_bootstrap(rows, question_id=lambda row: row["question_id"], statistic=statistic)
    clustered_ci = (clustered.ci_low, clustered.ci_high)
    old_contains, new_contains = _contains(official_ci, null_value), _contains(clustered_ci, null_value)
    changed = old_contains is not None and new_contains is not None and old_contains != new_contains
    official_width = official_ci[1] - official_ci[0] if official_ci[0] is not None and official_ci[1] is not None else None
    clustered_width = clustered.ci_high - clustered.ci_low if clustered.ci_low is not None and clustered.ci_high is not None else None
    return {
        "metric_id": metric_id,
        "role": role,
        "official_point_estimate": official_point,
        "observation_level_denominator": observation_denominator,
        "current_official_ci_95": {"low": official_ci[0], "high": official_ci[1]},
        "current_ci_method": official_method,
        "current_resampling_unit": official_unit,
        "question_clustered_bootstrap_ci_95": {"low": clustered.ci_low, "high": clustered.ci_high},
        "question_clusters": clustered.question_clusters,
        "bootstrap_replicates": clustered.bootstrap_replicates,
        "valid_replicates": clustered.valid_replicates,
        "non_estimable_replicates": clustered.non_estimable_replicates,
        "current_interval_width": official_width,
        "clustered_interval_width": clustered_width,
        "interval_width_difference": clustered_width - official_width if official_width is not None and clustered_width is not None else None,
        "null_value": null_value,
        "null_in_current_ci": old_contains,
        "null_in_clustered_ci": new_contains,
        "statistical_interpretation_changed": changed,
        "within_question_multiplicity": max(Counter(row["question_id"] for row in rows).values()),
        "methodological_notes": notes,
    }


def analyze(session: Session) -> dict[str, Any]:
    official = json.loads(OFFICIAL_ARTIFACT.read_text(encoding="utf-8"))
    controlled, provenance = _controlled_observations(session)
    controlled["RQ6"] = _rq6_observations(session)
    controlled["RQ7_SECONDARY"] = _secondary_observations(session, provenance["corrected_manifest"])
    results = official["results"]

    specifications = [
        ("RQ1.exact_agreement", "main", controlled["RQ1"], _rq1_agreement, results["RQ1"]["exact_agreement"], None, "Valid RQ1 judge-decision observations are retained within sampled original-question clusters; the raw agreement rate has no fixed formal null."),
        ("RQ1.cohens_kappa", "main", controlled["RQ1"], _rq1_kappa, results["RQ1"]["cohens_kappa"], 0.0, "Three-class Cohen's kappa is recomputed from the clustered confusion counts in every replicate."),
        ("RQ2.strict_complete_repetition_consistency", "main", controlled["RQ2"], lambda rows: _safe_mean(row["strict"] for row in rows if row["strict"] is not None), results["RQ2"]["strict_complete_repetition_consistency"], None, "Complete five-repetition cells remain intact and all cells from a sampled question move together."),
        ("RQ2.conditional_returned_judgment_consistency", "sensitivity", controlled["RQ2"], lambda rows: _safe_mean(row["conditional"] for row in rows if row["conditional"] is not None), results["RQ2"]["conditional_returned_judgment_consistency"], None, "Conditional repetition cells remain intact; this stays a secondary sensitivity estimand."),
        ("RQ3.paired_decisive_flip_rate", "main", controlled["RQ3"], _rq3_flip, results["RQ3"]["paired_decisive_flip_rate"], 0.0, "AB/BA pairs remain intact and are clustered with both turns and every judge from the same original question."),
        ("RQ4.variant_win_rate", "secondary", controlled["RQ4"], _variant_rate, results["RQ4"]["variant_win_rate"], 0.0, "Matched redundant-length pairs remain intact within original-question clusters."),
        ("RQ5.variant_win_rate", "secondary", controlled["RQ5"], _variant_rate, results["RQ5"]["variant_win_rate"], 0.0, "Matched presentation-format pairs remain intact within original-question clusters."),
        ("RQ6.stable_same_family_preference", "exploratory", controlled["RQ6"], _rq6_rate, results["RQ6"]["stable_same_family_preference"], 0.5, "Counterbalanced judge-pair units retain their AB/BA passes; 0.5 is the no-overall-preference reference."),
        ("RQ7_PRIMARY.agreement_delta", "main", controlled["RQ7_PRIMARY"], _rq7_primary_delta, results["RQ7_PRIMARY"]["agreement_delta"], 0.0, "Matched baseline and stable DUAL_SWAP decisions remain linked within original-question clusters."),
        ("RQ7_PRIMARY.coverage_delta", "main", controlled["RQ7_PRIMARY"], _rq7_primary_coverage_delta, results["RQ7_PRIMARY"]["coverage_delta"], 0.0, "Coverage is recomputed over complete linked triplets. The official artifact reports no CI for this descriptive delta."),
    ]
    comparisons: list[dict[str, Any]] = []
    units = {
        "RQ1.exact_agreement": "valid judge-decision observation",
        "RQ1.cohens_kappa": "valid judge-decision observation",
        "RQ2.strict_complete_repetition_consistency": "exact five-repetition cell",
        "RQ2.conditional_returned_judgment_consistency": "exact repetition cell",
        "RQ3.paired_decisive_flip_rate": "decisive AB/BA experimental unit",
        "RQ4.variant_win_rate": "valid matched variant pair",
        "RQ5.variant_win_rate": "valid matched variant pair",
        "RQ6.stable_same_family_preference": "stable decisive counterbalanced unit",
        "RQ7_PRIMARY.agreement_delta": "matched retained baseline/DUAL_SWAP decision",
        "RQ7_PRIMARY.coverage_delta": "not previously bootstrapped",
    }
    for metric_id, role, rows, statistic, metric, null, notes in specifications:
        comparisons.append(_comparison(
            metric_id=metric_id, role=role, rows=rows, statistic=statistic,
            official_point=float(metric["value"]), official_ci=_official_ci(metric),
            official_method="nonparametric percentile bootstrap" if metric.get("ci_low") is not None else "no official confidence interval",
            official_unit=units[metric_id], observation_denominator=int(metric["denominator"]),
            null_value=null, notes=notes,
        ))

    secondary = results["RQ7_SECONDARY"]
    for metric_id, statistic, point_key, ci_key, denominator, null, unit, notes in (
        ("RQ7_SECONDARY.agreement", _secondary_agreement, "agreement", "agreement_ci_95", secondary["consensus_covered_n"], None, "retained consensus-covered pair", "Consensus agreement is recomputed on retained pairs while all pairs from each original question move together."),
        ("RQ7_SECONDARY.coverage", _secondary_coverage, "coverage", "coverage_ci_95", secondary["planned_n"], None, "planned canonical answer pair", "Consensus coverage is recomputed over all planned pairs in sampled original-question clusters."),
        ("RQ7_SECONDARY.matched_delta", _secondary_delta, "matched_delta", "matched_delta_ci_95", secondary["consensus_covered_n"], 0.0, "retained consensus-covered pair", "Consensus-minus-equal-weight-individual agreement is recomputed only on retained pairs; it is not compared directly with DUAL_SWAP."),
    ):
        ci = secondary[ci_key]
        comparisons.append(_comparison(
            metric_id=metric_id, role="secondary/exploratory", rows=controlled["RQ7_SECONDARY"], statistic=statistic,
            official_point=float(secondary[point_key]), official_ci=(ci["low"], ci["high"]),
            official_method="nonparametric percentile bootstrap", official_unit=unit,
            observation_denominator=int(denominator), null_value=null, notes=notes,
        ))

    interpretation_changes = [row["metric_id"] for row in comparisons if row["statistical_interpretation_changed"]]
    artifact = {
        "artifact_id": ANALYSIS_ID,
        "status": "SENSITIVITY_VALIDATION_ONLY_NOT_AUTHORITATIVE_REPLACEMENT_EVIDENCE",
        "source_official_artifact": {
            "path": OFFICIAL_ARTIFACT.relative_to(ROOT).as_posix(),
            "artifact_sha256": official["artifact_sha256"],
        },
        "method": {
            "name": "original-MT-Bench-question clustered nonparametric percentile bootstrap",
            "cluster_unit": "original MT-Bench question_id (80-question frame; turns are not separate clusters)",
            "seed": SEED,
            "resamples": RESAMPLES,
            "confidence_level": 0.95,
            "sampling": "sample the represented question clusters with replacement, preserving the original cluster count and all estimator-specific observations within every sampled question",
            "eligibility": "reapply each existing estimand's eligibility rule inside each clustered replicate",
            "non_estimable_policy": "count and report; never silently coerce or impute",
        },
        "ci_method_audit": {
            "current_general_method": "deterministic nonparametric percentile bootstrap with 10,000 resamples",
            "current_units_vary_by_estimand": True,
            "same_original_question_can_contribute_multiple_current_resampling_units": True,
            "reason_for_sensitivity": "judges, turns, repetitions, swaps, variants, and answer pairs can share an original MT-Bench question",
        },
        "metrics": comparisons,
        "decision_gate": {
            "metrics_with_changed_null_status": interpretation_changes,
            "substantive_conclusions_unchanged": not interpretation_changes,
            "official_results_replaced": False,
        },
        "integrity": {
            "controlled_logical_passes": provenance["logical_accounting"]["logical_controlled_passes"],
            "provider_calls": 0,
            "database_writes": 0,
            "experiments_rerun": 0,
        },
    }
    body = json.dumps(artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    artifact["artifact_sha256"] = hashlib.sha256(body).hexdigest()
    return artifact


def _display_value(metric_id: str, value: float | None) -> str:
    if value is None:
        return "not reported"
    return f"{value:.4f}" if metric_id == "RQ1.cohens_kappa" else f"{100 * value:.2f}%"


def _display_interval(metric_id: str, interval: Mapping[str, float | None]) -> str:
    if interval["low"] is None or interval["high"] is None:
        return "not reported"
    return f"{_display_value(metric_id, interval['low'])} to {_display_value(metric_id, interval['high'])}"


def _display_width_change(metric_id: str, width: float | None) -> str:
    if width is None:
        return "not comparable"
    direction = "wider" if width > 0 else "narrower" if width < 0 else "unchanged"
    if direction == "unchanged":
        return direction
    magnitude = f"{abs(width):.4f}" if metric_id == "RQ1.cohens_kappa" else f"{100 * abs(width):.2f} pp"
    return f"{direction} by {magnitude}"


def render_report(artifact: dict[str, Any]) -> str:
    lines = [
        "# Current CI vs Question-Clustered Bootstrap CI",
        "",
        "> Sensitivity/validation analysis only. This report does not replace frozen confidence intervals or authoritative AnalysisRuns.",
        "",
        f"Method: 10,000 deterministic percentile-bootstrap replicates (seed `{SEED}`), resampling original MT-Bench question IDs and retaining every eligible observation from each sampled question.",
        "",
        "| Metric | Current 95% CI | Question-clustered 95% CI | Width change | Null status | Interpretation |",
        "| --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in artifact["metrics"]:
        current = row["current_official_ci_95"]
        clustered = row["question_clustered_bootstrap_ci_95"]
        width = row["interval_width_difference"]
        width_text = _display_width_change(row["metric_id"], width)
        if row["null_value"] is None:
            null_text = "descriptive; no tested null"
        elif row["null_in_current_ci"] is None:
            null_text = f"clustered null {'inside' if row['null_in_clustered_ci'] else 'outside'}; no official CI"
        else:
            null_text = f"{'inside' if row['null_in_current_ci'] else 'outside'} → {'inside' if row['null_in_clustered_ci'] else 'outside'}"
        interpretation = "CHANGED" if row["statistical_interpretation_changed"] else "unchanged"
        lines.append(
            f"| `{row['metric_id']}` | {_display_interval(row['metric_id'], current)} | {_display_interval(row['metric_id'], clustered)} | {width_text} | {null_text} | {interpretation} |"
        )
    changed = artifact["decision_gate"]["metrics_with_changed_null_status"]
    lines.extend([
        "",
        "## Interpretation",
        "",
        "The clustering concern affects interval width to different degrees because the number of observations contributed by each question is uneven and multiple judges, turns, repetitions, swaps, or pairs can share a question. Point estimates and eligibility rules are unchanged.",
        "",
        ("The following metrics changed null-value status: " + ", ".join(changed) + ". This requires review before any propagation." if changed else "No included metric changed whether its relevant null value was inside or outside the interval. The substantive scientific conclusions therefore remain unchanged in this sensitivity analysis."),
        "",
        "RQ7 Primary coverage delta previously had no official confidence interval. Its clustered interval is reported here only to evaluate uncertainty around the existing descriptive coverage trade-off; it is not an official replacement interval.",
        "",
        "Multi-Judge remains a secondary/exploratory mitigation analysis with its own retained population and comparator. Its clustered interval must not be ranked directly against DUAL_SWAP.",
        "",
    ])
    return "\n".join(lines)


def write_outputs(artifact: dict[str, Any]) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUTPUT_REPORT.write_text(render_report(artifact), encoding="utf-8")


def main() -> int:
    from backend.core.database import SessionLocal

    with SessionLocal() as session:
        artifact = analyze(session)
    write_outputs(artifact)
    print(json.dumps({
        "artifact": OUTPUT_JSON.relative_to(ROOT).as_posix(),
        "artifact_sha256": artifact["artifact_sha256"],
        "substantive_conclusions_unchanged": artifact["decision_gate"]["substantive_conclusions_unchanged"],
        "provider_calls": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
