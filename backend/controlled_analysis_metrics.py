"""Authoritative controlled-only metrics and bootstrap analysis for RQ1--RQ7.

No provider client, legacy ``judge_decisions`` query, or default-value success
path exists here.  Phase 3 helpers remain planning-time checks; final evidence
must enter this module as controlled, provenance-identified units.
"""
from __future__ import annotations

import random
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from math import fsum, isfinite
from statistics import mean
from typing import Any, Callable, Iterable, Literal, Sequence


ANALYSIS_VERSION = "phase4-analysis-v1"
CONFIDENCE_LEVEL = 0.95
BOOTSTRAP_ITERATIONS = 10_000
VALID = frozenset({"ANSWER_A", "ANSWER_B", "TIE"})
FAILURES = frozenset({"UNKNOWN", "INVALID_RESPONSE", "API_ERROR", "TIMEOUT", "REFUSAL", "AMBIGUOUS", "MISSING_PASS"})


@dataclass(frozen=True)
class MetricResult:
    metric_name: str
    value: float | None
    numerator: int | None
    denominator: int | None
    eligible_n: int
    analyzed_n: int
    tie_count: int = 0
    unknown_count: int = 0
    invalid_count: int = 0
    failure_count: int = 0
    refusal_count: int = 0
    missing_count: int = 0
    excluded_count: int = 0
    ci_low: float | None = None
    ci_high: float | None = None
    confidence_level: float = CONFIDENCE_LEVEL
    status: str = "ESTIMABLE"
    notes: str = ""
    group: str | None = None
    judge: str | None = None
    condition: str | None = None
    temperature: float | None = None
    category: str | None = None
    comparison: str | None = None
    metric_version: str = ANALYSIS_VERSION
    analysis_seed: int | None = None
    bootstrap_iterations: int | None = None

    def serialize(self) -> dict[str, Any]: return asdict(self)


def _counts(labels: Iterable[str | None]) -> dict[str, int]:
    values = list(labels)
    return {"tie_count": values.count("TIE"), "unknown_count": values.count("UNKNOWN"), "invalid_count": values.count("INVALID_RESPONSE"), "failure_count": sum(v in {"API_ERROR", "TIMEOUT", "REFUSAL", "AMBIGUOUS"} for v in values), "refusal_count": values.count("REFUSAL"), "missing_count": sum(v is None or v == "MISSING_PASS" for v in values)}


def _not_estimable(name: str, *, eligible_n: int, analyzed_n: int = 0, status: str = "NOT_ESTIMABLE", notes: str = "", labels: Iterable[str | None] = ()) -> MetricResult:
    return MetricResult(name, None, None, None, eligible_n, analyzed_n, excluded_count=max(0, eligible_n - analyzed_n), status=status, notes=notes, **_counts(labels))


def bootstrap_ci(units: Sequence[Any], statistic: Callable[[Sequence[Any]], float | None], *, seed: int, iterations: int = BOOTSTRAP_ITERATIONS, confidence_level: float = CONFIDENCE_LEVEL) -> tuple[float | None, float | None]:
    """Percentile bootstrap; callers pass independent units, never split passes."""
    if len(units) < 2 or not 0 < confidence_level < 1 or iterations < 1: return None, None
    rng = random.Random(seed); samples: list[float] = []
    for _ in range(iterations):
        value = statistic([units[rng.randrange(len(units))] for _ in units])
        if value is not None and isfinite(value): samples.append(value)
    if not samples: return None, None
    samples.sort(); alpha = (1 - confidence_level) / 2
    return samples[int(alpha * (len(samples) - 1))], samples[int((1 - alpha) * (len(samples) - 1))]


def _rate(name: str, units: Sequence[Any], success: Callable[[Any], bool], *, eligible_n: int, labels: Iterable[str | None], seed: int, iterations: int, notes: str, denominator: int | None = None) -> MetricResult:
    n = len(units) if denominator is None else denominator
    if n == 0: return _not_estimable(name, eligible_n=eligible_n, status="NO_DATA", notes=notes, labels=labels)
    numerator = sum(success(unit) for unit in units); value = numerator / n
    low, high = bootstrap_ci(units, lambda sample: sum(success(x) for x in sample) / len(sample) if sample else None, seed=seed, iterations=iterations)
    return MetricResult(name, value, numerator, n, eligible_n, len(units), ci_low=low, ci_high=high, notes=notes, analysis_seed=seed, bootstrap_iterations=iterations, **_counts(labels))


@dataclass(frozen=True)
class ControlledEvidence:
    evidence_class: str
    unit_id: str
    rq_code: str
    judge_name: str
    condition: str


def require_controlled(records: Iterable[ControlledEvidence]) -> list[ControlledEvidence]:
    rows = list(records)
    forbidden = [r.unit_id for r in rows if r.evidence_class != "CONTROLLED"]
    if forbidden: raise ValueError(f"Authoritative analysis accepts CONTROLLED evidence only; rejected {forbidden!r}")
    return rows


@dataclass(frozen=True)
class RQ1Unit(ControlledEvidence):
    human_label: str | None
    judge_label: str | None
    category: str


def analyze_rq1(units: Iterable[RQ1Unit], *, seed: int = 20260818, iterations: int = BOOTSTRAP_ITERATIONS) -> dict[str, MetricResult]:
    rows = require_controlled(units); valid = [u for u in rows if u.human_label in VALID and u.judge_label in VALID]
    labels = [u.judge_label for u in rows]
    agreement = _rate("rq1_exact_agreement", valid, lambda u: u.human_label == u.judge_label, eligible_n=len(rows), labels=labels, seed=seed, iterations=iterations, notes="Three-class A/B/TIE agreement; failures are reported outside the valid comparable denominator.")
    if not valid: return {"exact_agreement": agreement, "cohens_kappa": _not_estimable("rq1_cohens_kappa", eligible_n=len(rows), status="NO_DATA", notes="No valid comparable Human Preference Reference Labels.", labels=labels)}
    classes = ("ANSWER_A", "ANSWER_B", "TIE")
    observed = agreement.value or 0.0; human = Counter(u.human_label for u in valid); judge = Counter(u.judge_label for u in valid)
    expected = sum(human[c] * judge[c] for c in classes) / len(valid) ** 2
    kappa = None if expected == 1 else (observed - expected) / (1 - expected)
    if kappa is None:
        kappa_result = _not_estimable("rq1_cohens_kappa", eligible_n=len(rows), analyzed_n=len(valid), status="NOT_ESTIMABLE", notes="Kappa is undefined when expected agreement is one.", labels=labels)
    else:
        def statistic(sample: Sequence[RQ1Unit]) -> float | None:
            observed_sample = sum(x.human_label == x.judge_label for x in sample) / len(sample)
            h, j = Counter(x.human_label for x in sample), Counter(x.judge_label for x in sample)
            expected_sample = sum(h[c] * j[c] for c in classes) / len(sample) ** 2
            return None if expected_sample == 1 else (observed_sample - expected_sample) / (1 - expected_sample)
        low, high = bootstrap_ci(valid, statistic, seed=seed, iterations=iterations)
        kappa_result = MetricResult("rq1_cohens_kappa", kappa, None, len(valid), len(rows), len(valid), ci_low=low, ci_high=high, notes="Cohen's kappa over ordered classes ANSWER_A, ANSWER_B, TIE; paired-unit percentile bootstrap CI.", analysis_seed=seed, bootstrap_iterations=iterations, **_counts(labels))
    result = {"exact_agreement": agreement, "cohens_kappa": kappa_result}
    for judge in sorted({row.judge_name for row in rows}):
        result[f"judge:{judge}:exact_agreement"] = _rate("rq1_exact_agreement", [row for row in valid if row.judge_name == judge], lambda row: row.human_label == row.judge_label, eligible_n=sum(row.judge_name == judge for row in rows), labels=[row.judge_label for row in rows if row.judge_name == judge], seed=seed, iterations=iterations, notes="Judge-stratified three-class agreement.")
    for category in sorted({row.category for row in rows}):
        result[f"category:{category}:exact_agreement"] = _rate("rq1_exact_agreement", [row for row in valid if row.category == category], lambda row: row.human_label == row.judge_label, eligible_n=sum(row.category == category for row in rows), labels=[row.judge_label for row in rows if row.category == category], seed=seed, iterations=iterations, notes="Category-stratified three-class agreement.")
    return result


@dataclass(frozen=True)
class RQ2Repetition(ControlledEvidence):
    group_key: str
    answer_a_id: int
    answer_b_id: int
    temperature: float
    repetition_index: int
    retry_count: int
    verdict: str | None
    provider: str = "UNKNOWN"
    requested_model: str = "UNKNOWN"
    prompt_template_version: str = "UNKNOWN"
    top_p: float | None = None
    seed_policy: str = "UNKNOWN"
    effective_model: str = "UNKNOWN"
    configured_upstream_provider: str | None = None
    observed_upstream_provider: str | None = None
    routing_policy_version: str | None = None
    routing_fingerprint: str | None = None
    expected_repetitions: int = 5


def _rq2_group_metric(groups: Sequence[list[RQ2Repetition]], *, strict: bool, seed: int, iterations: int, judge: str | None = None) -> MetricResult:
    labels = [row.verdict for group in groups for row in group]
    values: list[float] = []
    for group in groups:
        identity = {(r.answer_a_id, r.answer_b_id, r.judge_name, r.provider, r.requested_model, r.effective_model, r.configured_upstream_provider, r.observed_upstream_provider, r.routing_policy_version, r.routing_fingerprint, r.condition, r.temperature, r.prompt_template_version, r.top_p, r.seed_policy) for r in group}
        repetitions = {r.repetition_index for r in group}
        valid = [r.verdict for r in group if r.verdict in VALID]
        complete = len(identity) == 1 and len(repetitions) == len(group) and len(group) == group[0].expected_repetitions
        if not complete or not valid or (strict and len(valid) != group[0].expected_repetitions):
            continue
        values.append(max(Counter(valid).values()) / len(valid))
    name = "rq2_strict_complete_repetition_consistency" if strict else "rq2_conditional_returned_judgment_consistency"
    notes = (
        "Primary estimand: mean modal-verdict proportion over exact groups whose every planned repetition returned a valid scientific verdict."
        if strict else
        "Secondary sensitivity estimand: mean modal-verdict proportion among valid returned judgments in exact planned repetition groups."
    )
    if not values:
        return _not_estimable(name, eligible_n=len(groups), status="INSUFFICIENT_ELIGIBLE_UNITS", notes=notes, labels=labels)
    low, high = bootstrap_ci(values, lambda sample: mean(sample), seed=seed, iterations=iterations)
    return MetricResult(name, mean(values), None, len(values), len(groups), len(values), excluded_count=len(groups) - len(values), ci_low=low, ci_high=high, notes=notes, judge=judge, analysis_seed=seed, bootstrap_iterations=iterations, **_counts(labels))


def analyze_rq2(units: Iterable[RQ2Repetition], *, seed: int = 20260818, iterations: int = BOOTSTRAP_ITERATIONS, primary_estimand: Literal["strict", "conditional"] = "strict", include_sensitivity: bool = True, include_by_judge: bool = True) -> dict[str, MetricResult]:
    """Report strict complete-repetition consistency plus the conditional sensitivity estimand.

    ``conditional`` exists solely for immutable historical recomputation.  New
    release analyses use the strict all-five-valid estimand as their primary.
    """
    if primary_estimand not in {"strict", "conditional"}:
        raise ValueError("primary_estimand must be 'strict' or 'conditional'")
    rows = require_controlled(units); grouped = defaultdict(list)
    for row in rows: grouped[row.group_key].append(row)
    groups = list(grouped.values())
    strict_metric = _rq2_group_metric(groups, strict=True, seed=seed, iterations=iterations)
    conditional_metric = _rq2_group_metric(groups, strict=False, seed=seed, iterations=iterations)
    result = {"consistency": strict_metric if primary_estimand == "strict" else conditional_metric}
    if include_sensitivity:
        result["strict_complete_repetition_consistency"] = strict_metric
        result["conditional_returned_judgment_consistency"] = conditional_metric
    if include_by_judge:
        for judge in sorted({row.judge_name for row in rows}):
            judge_groups = [group for group in groups if group[0].judge_name == judge]
            judge_strict = _rq2_group_metric(judge_groups, strict=True, seed=seed, iterations=iterations, judge=judge)
            judge_conditional = _rq2_group_metric(judge_groups, strict=False, seed=seed, iterations=iterations, judge=judge)
            result[f"judge:{judge}:consistency"] = judge_strict if primary_estimand == "strict" else judge_conditional
            if include_sensitivity:
                result[f"judge:{judge}:strict_complete_repetition_consistency"] = judge_strict
                result[f"judge:{judge}:conditional_returned_judgment_consistency"] = judge_conditional
    return result


@dataclass(frozen=True)
class RQ3Pair(ControlledEvidence):
    pass_ab: str | None
    pass_ba: str | None
    slot_wins_a: int = 0
    slot_wins_b: int = 0


def analyze_rq3(units: Iterable[RQ3Pair], *, seed: int = 20260818, iterations: int = BOOTSTRAP_ITERATIONS, include_by_judge: bool = False) -> dict[str, MetricResult]:
    rows = require_controlled(units); complete = [u for u in rows if u.pass_ab is not None and u.pass_ba is not None]; decisive = [u for u in complete if u.pass_ab in {"ANSWER_A", "ANSWER_B"} and u.pass_ba in {"ANSWER_A", "ANSWER_B"}]
    labels = [x for u in rows for x in (u.pass_ab, u.pass_ba)]
    flip = _rate("rq3_paired_decisive_flip_rate", decisive, lambda u: u.pass_ab != u.pass_ba, eligible_n=len(rows), labels=labels, seed=seed, iterations=iterations, notes="Denominator: complete pairs with two decisive mapped-original outcomes.")
    broad = [u for u in complete if u.pass_ab in VALID and u.pass_ba in VALID]
    disagreement = _rate("rq3_all_paired_disagreement_rate", broad, lambda u: u.pass_ab != u.pass_ba, eligible_n=len(rows), labels=labels, seed=seed, iterations=iterations, notes="Broader valid-label disagreement; distinct from decisive flip rate.")
    slot_a, slot_b = sum(u.slot_wins_a for u in decisive), sum(u.slot_wins_b for u in decisive); slot = _not_estimable("rq3_slot_win_imbalance", eligible_n=len(rows), status="NO_DECISIVE_SLOT_OUTCOMES", notes="No decisive presented-slot outcomes.", labels=labels) if not slot_a + slot_b else MetricResult("rq3_slot_win_imbalance", abs(slot_a-slot_b)/(slot_a+slot_b), abs(slot_a-slot_b), slot_a+slot_b, len(rows), len(decisive), notes="Absolute presented-slot win difference / decisive presented-slot outcomes; not a flip rate.", **_counts(labels))
    result = {"paired_decisive_flip_rate": flip, "all_paired_disagreement_rate": disagreement, "slot_win_imbalance": slot, "incomplete_pairs": MetricResult("rq3_incomplete_pair_count", float(len(rows)-len(complete)), len(rows)-len(complete), len(rows), len(rows), len(rows), notes="Pairs missing either presentation pass.", **_counts(labels))}
    if include_by_judge:
        for judge in sorted({row.judge_name for row in rows}):
            judge_metrics = analyze_rq3([row for row in rows if row.judge_name == judge], seed=seed, iterations=iterations)
            for key, metric in judge_metrics.items():
                result[f"judge:{judge}:{key}"] = MetricResult(**{**metric.serialize(), "judge": judge})
    return result


@dataclass(frozen=True)
class VariantPair(ControlledEvidence):
    variant_valid: bool
    variant_outcome: Literal["VARIANT", "ORIGINAL", "TIE"] | None
    order: str
    transform_valid: bool = True
    exclusion_reason: str | None = None


def _analyze_variant(rq: str, units: Iterable[VariantPair], *, seed: int, iterations: int, include_exclusion_breakdown: bool = False) -> dict[str, MetricResult]:
    rows = require_controlled(units); valid = [u for u in rows if u.variant_valid and u.variant_outcome in {"VARIANT", "ORIGINAL", "TIE"}]; labels = [u.variant_outcome for u in rows]
    name = f"{rq.lower()}_controlled_variant_win_rate"
    result = _rate(name, valid, lambda u: u.variant_outcome == "VARIANT", eligible_n=len(rows), labels=labels, seed=seed, iterations=iterations, notes="Validated controlled variant wins / valid controlled variant pairs.")
    output = {"variant_win_rate": result, "original_win_rate": _rate(f"{rq.lower()}_original_win_rate", valid, lambda u: u.variant_outcome == "ORIGINAL", eligible_n=len(rows), labels=labels, seed=seed, iterations=iterations, notes="Reported separately from variant wins."), "excluded_pair_count": MetricResult(f"{rq.lower()}_excluded_pair_count", float(sum(not u.variant_valid for u in rows)), sum(not u.variant_valid for u in rows), len(rows), len(rows), len(rows), notes="Total non-analyzed paired units; see explicit exclusion categories.")}
    if include_exclusion_breakdown:
        for reason in ("deterministic_transform_rejection", "presentation_order_disagreement", "operational_failure", "invalid_or_incomplete_pair"):
            count = sum(unit.exclusion_reason == reason for unit in rows)
            output[f"{reason}_count"] = MetricResult(f"{rq.lower()}_{reason}_count", float(count), count, len(rows), len(rows), len(rows), notes="Explicit paired-unit exclusion category.")
        stable_decisive = sum(unit.variant_valid and unit.variant_outcome in {"VARIANT", "ORIGINAL"} for unit in rows)
        stable_tie = sum(unit.variant_valid and unit.variant_outcome == "TIE" for unit in rows)
        output["stable_decisive_pair_count"] = MetricResult(f"{rq.lower()}_stable_decisive_pair_count", float(stable_decisive), stable_decisive, len(rows), len(rows), len(rows), notes="Valid stable decisive paired units.")
        output["stable_tie_pair_count"] = MetricResult(f"{rq.lower()}_stable_tie_pair_count", float(stable_tie), stable_tie, len(rows), len(rows), len(rows), notes="Valid stable tie paired units.")
    return output


def analyze_rq4(units: Iterable[VariantPair], *, seed: int = 20260818, iterations: int = BOOTSTRAP_ITERATIONS, include_exclusion_breakdown: bool = False) -> dict[str, MetricResult]: return _analyze_variant("RQ4", units, seed=seed, iterations=iterations, include_exclusion_breakdown=include_exclusion_breakdown)
def analyze_rq5(units: Iterable[VariantPair], *, seed: int = 20260818, iterations: int = BOOTSTRAP_ITERATIONS, include_exclusion_breakdown: bool = False) -> dict[str, MetricResult]: return _analyze_variant("RQ5", units, seed=seed, iterations=iterations, include_exclusion_breakdown=include_exclusion_breakdown)


@dataclass(frozen=True)
class RQ6Unit(ControlledEvidence):
    source_family_complete: bool
    outcome: Literal["SELF", "OTHER", "TIE"] | None
    self_slot: str | None


def analyze_rq6(units: Iterable[RQ6Unit], *, seed: int = 20260818, iterations: int = BOOTSTRAP_ITERATIONS) -> dict[str, MetricResult]:
    rows = require_controlled(units); valid = [u for u in rows if u.source_family_complete and u.outcome in {"SELF", "OTHER", "TIE"}]; slots = Counter(u.self_slot for u in valid); labels = [u.outcome for u in rows]
    if abs(slots["A"]-slots["B"]) > 1: return {"self_family_preference": _not_estimable("rq6_matched_self_family_preference", eligible_n=len(rows), status="UNBALANCED_PRESENTATION", notes="Self-family slots are not balanced.", labels=labels)}
    return {"self_family_preference": _rate("rq6_matched_self_family_preference", valid, lambda u: u.outcome == "SELF", eligible_n=len(rows), labels=labels, seed=seed, iterations=iterations, notes="Balanced matched self-family preference; not an A-slot comparator.")}


@dataclass(frozen=True)
class RQ7Pair(ControlledEvidence):
    base_pair_key: str
    baseline: dict[str, float] | None
    mitigation: dict[str, float] | None


@dataclass(frozen=True)
class RQ7Observation(ControlledEvidence):
    """One matched baseline/dual-swap unit before aggregate metrics exist."""
    base_pair_key: str
    human_label: str | None
    baseline_label: str | None
    dual_ab_label: str | None
    dual_ba_label: str | None


def _rq7_strategy(rows: Sequence[RQ7Observation], labels: Sequence[str | None], *, prefix: str, dual: bool, seed: int, iterations: int) -> dict[str, MetricResult]:
    eligible = len(rows)
    valid = [(row, label) for row, label in zip(rows, labels) if row.human_label in VALID and label in VALID]
    metric_rows = [RQ1Unit("CONTROLLED", row.unit_id, "RQ7", row.judge_name, row.condition, row.human_label, label, "RQ7") for row, label in valid]
    agreement = analyze_rq1(metric_rows, seed=seed, iterations=iterations)
    all_valid = [label for label in labels if label in VALID]
    completed = [label for label in labels if label is not None]
    output: dict[str, MetricResult] = {
        f"{prefix}_agreement": agreement["exact_agreement"],
        f"{prefix}_cohens_kappa": agreement["cohens_kappa"],
        f"{prefix}_tie_rate": _rate(f"rq7_{prefix}_tie_rate", all_valid, lambda label: label == "TIE", eligible_n=eligible, labels=labels, seed=seed, iterations=iterations, notes="Tie rate among valid three-class strategy outcomes."),
        f"{prefix}_failure_rate": _rate(f"rq7_{prefix}_failure_rate", list(labels), lambda label: label not in VALID, eligible_n=eligible, labels=labels, seed=seed, iterations=iterations, notes="Operational failures / eligible matched units."),
        f"{prefix}_coverage": _rate(f"rq7_{prefix}_coverage", list(labels), lambda label: label in VALID, eligible_n=eligible, labels=labels, seed=seed, iterations=iterations, notes="Valid three-class outcomes / eligible matched units."),
        f"{prefix}_decisive_coverage": _rate(f"rq7_{prefix}_decisive_coverage", list(labels), lambda label: label in {"ANSWER_A", "ANSWER_B"}, eligible_n=eligible, labels=labels, seed=seed, iterations=iterations, notes="Decisive outcomes / eligible matched units."),
    }
    if dual:
        paired = [(row.dual_ab_label, row.dual_ba_label) for row in rows if row.dual_ab_label in VALID and row.dual_ba_label in VALID]
        disagreements = [a != b for a, b in paired]
        output[f"{prefix}_dual_pass_disagreement"] = _rate(f"rq7_{prefix}_dual_pass_disagreement", disagreements, lambda value: value, eligible_n=eligible, labels=[label for row in rows for label in (row.dual_ab_label, row.dual_ba_label)], seed=seed, iterations=iterations, notes="AB/BA disagreement among complete valid dual passes.")
        output[f"{prefix}_dual_pass_stability"] = _rate(f"rq7_{prefix}_dual_pass_stability", disagreements, lambda value: not value, eligible_n=eligible, labels=[label for row in rows for label in (row.dual_ab_label, row.dual_ba_label)], seed=seed, iterations=iterations, notes="1 - dual-pass disagreement among complete valid dual passes.")
    return output


def _rq7_observation_analysis(rows: Sequence[RQ7Observation], *, seed: int, iterations: int) -> dict[str, MetricResult]:
    baseline = [row.baseline_label for row in rows]
    # A DUAL_SWAP judgement is valid only when the two mapped-original passes
    # agree.  Tie/Tie remains a valid tie; every other pair is an explicit
    # missing/failed mitigation outcome, never a fabricated winner.
    mitigation: list[str | None] = []
    for row in rows:
        if row.dual_ab_label == row.dual_ba_label and row.dual_ab_label in VALID:
            mitigation.append(row.dual_ab_label)
        elif row.dual_ab_label is None or row.dual_ba_label is None:
            mitigation.append(None)
        elif row.dual_ab_label in FAILURES or row.dual_ba_label in FAILURES:
            mitigation.append("API_ERROR")
        else:
            mitigation.append("MISSING_PASS")
    result = _rq7_strategy(rows, baseline, prefix="baseline", dual=False, seed=seed, iterations=iterations)
    result.update(_rq7_strategy(rows, mitigation, prefix="dual_swap", dual=True, seed=seed, iterations=iterations))
    comparable = ("agreement", "cohens_kappa", "tie_rate", "failure_rate", "coverage", "decisive_coverage")
    for name in comparable:
        left, right = result[f"baseline_{name}"], result[f"dual_swap_{name}"]
        if left.value is None or right.value is None:
            result[f"{name}_delta"] = _not_estimable(f"rq7_{name}_delta", eligible_n=len(rows), status="NOT_ESTIMABLE", notes="Mitigation-baseline requires finite values under both matched strategies.")
        else:
            result[f"{name}_delta"] = MetricResult(f"rq7_{name}_delta", right.value - left.value, None, min(left.analyzed_n, right.analyzed_n), len(rows), min(left.analyzed_n, right.analyzed_n), notes="delta = DUAL_SWAP - BASELINE; sign is preserved and only comparable metrics are reported.", comparison="dual_swap-baseline")
    return result


def analyze_rq7_matched(units: Iterable[RQ7Observation], *, seed: int = 20260818, iterations: int = BOOTSTRAP_ITERATIONS) -> dict[str, MetricResult]:
    """Matched RQ7 release analysis.

    Strategy-specific operating points retain all eligible units for coverage.
    Agreement comparisons are restricted to the same units with a valid human
    label, valid baseline outcome, and stable valid DUAL_SWAP outcome.  This is
    an explicit matched retained-decision comparison, not a causal claim.
    """
    rows = require_controlled(units)
    if not all(isinstance(row, RQ7Observation) for row in rows):
        raise ValueError("Matched RQ7 analysis requires raw RQ7 observations")
    observations: list[RQ7Observation] = rows  # type: ignore[assignment]
    dual_labels: list[str | None] = []
    for row in observations:
        if row.dual_ab_label == row.dual_ba_label and row.dual_ab_label in VALID:
            dual_labels.append(row.dual_ab_label)
        elif row.dual_ab_label is None or row.dual_ba_label is None:
            dual_labels.append(None)
        elif row.dual_ab_label in FAILURES or row.dual_ba_label in FAILURES:
            dual_labels.append("API_ERROR")
        else:
            dual_labels.append("MISSING_PASS")
    baseline_labels = [row.baseline_label for row in observations]
    result: dict[str, MetricResult] = {}
    # Descriptive operating points remain useful, but they do not share an
    # effective returned-decision population and are never used as a delta.
    descriptive = _rq7_strategy(observations, baseline_labels, prefix="baseline_operating_point", dual=False, seed=seed, iterations=iterations)
    descriptive.update(_rq7_strategy(observations, dual_labels, prefix="dual_swap_operating_point", dual=True, seed=seed, iterations=iterations))
    result.update(descriptive)
    result["baseline_coverage"] = result.pop("baseline_operating_point_coverage")
    result["dual_swap_coverage"] = result.pop("dual_swap_operating_point_coverage")
    # Retain a concise, stable public key while preserving the explicit
    # operating-point namespace for the non-comparable descriptive metrics.
    result["dual_swap_dual_pass_stability"] = result["dual_swap_operating_point_dual_pass_stability"]
    baseline_coverage, dual_coverage = result["baseline_coverage"], result["dual_swap_coverage"]
    result["coverage_delta"] = MetricResult("rq7_coverage_delta", (dual_coverage.value - baseline_coverage.value) if baseline_coverage.value is not None and dual_coverage.value is not None else None, None, len(observations), len(observations), len(observations), notes="Descriptive coverage delta = DUAL_SWAP - BASELINE over the same planned matched units.", comparison="dual_swap-baseline", analysis_seed=seed, bootstrap_iterations=iterations, **_counts([*baseline_labels, *dual_labels]))
    matched = [(row, dual) for row, dual in zip(observations, dual_labels) if row.human_label in VALID and row.baseline_label in VALID and dual in VALID]
    labels = [label for row, dual in matched for label in (row.baseline_label, dual)]
    baseline = _rate("rq7_matched_retained_baseline_agreement", matched, lambda pair: pair[0].baseline_label == pair[0].human_label, eligible_n=len(observations), labels=labels, seed=seed, iterations=iterations, notes="Agreement on the exact matched retained-decision subset; not an all-unit operating point.")
    dual = _rate("rq7_matched_retained_dual_swap_agreement", matched, lambda pair: pair[1] == pair[0].human_label, eligible_n=len(observations), labels=labels, seed=seed, iterations=iterations, notes="Agreement on the exact matched retained-decision subset; not an all-unit operating point.")
    result["baseline_agreement"] = baseline
    result["dual_swap_agreement"] = dual
    deltas = [int(dual_label == row.human_label) - int(row.baseline_label == row.human_label) for row, dual_label in matched]
    if deltas:
        low, high = bootstrap_ci(deltas, lambda sample: mean(sample), seed=seed, iterations=iterations)
        result["agreement_delta"] = MetricResult("rq7_matched_retained_agreement_delta", mean(deltas), sum(deltas), len(deltas), len(observations), len(deltas), ci_low=low, ci_high=high, notes="Paired matched retained-decision agreement difference (DUAL_SWAP - BASELINE). It conditions on both strategies returning valid decisions and is not a causal treatment-effect claim.", comparison="dual_swap-baseline", analysis_seed=seed, bootstrap_iterations=iterations, **_counts(labels))
    else:
        result["agreement_delta"] = _not_estimable("rq7_matched_retained_agreement_delta", eligible_n=len(observations), status="NO_COMMON_VALID_UNITS", notes="No units have valid human, baseline, and stable DUAL_SWAP outcomes.", labels=labels)
    discordant = {
        "baseline_only_correct": sum(row.baseline_label == row.human_label and dual_label != row.human_label for row, dual_label in matched),
        "dual_swap_only_correct": sum(row.baseline_label != row.human_label and dual_label == row.human_label for row, dual_label in matched),
    }
    for key, value in discordant.items():
        result[f"{key}_count"] = MetricResult(f"rq7_{key}_count", float(value), value, len(matched), len(observations), len(matched), notes="Discordant matched retained-decision count.", **_counts(labels))
    return result


def _analyze_rq7_preaggregated(rows: list[RQ7Pair]) -> dict[str, MetricResult]:
    paired = [u for u in rows if u.baseline is not None and u.mitigation is not None]
    if not paired: return {"delta": _not_estimable("rq7_matched_absolute_delta", eligible_n=len(rows), status="NOT_ESTIMABLE", notes="No comparable baseline/mitigation pairs.")}
    names = sorted(set.intersection(*(set(u.baseline) & set(u.mitigation) for u in paired)))
    results: dict[str, MetricResult] = {}
    for name in names:
        changes = [u.mitigation[name]-u.baseline[name] for u in paired if isfinite(u.baseline[name]) and isfinite(u.mitigation[name])]
        value = fsum(changes) / len(changes) if changes else None
        if value is not None and abs(value) < 1e-12: value = 0.0
        results[name] = _not_estimable(f"rq7_{name}_absolute_delta", eligible_n=len(rows), status="NOT_ESTIMABLE", notes="No finite matched values.") if value is None else MetricResult(f"rq7_{name}_absolute_delta", value, None, len(changes), len(rows), len(changes), notes="absolute_delta = mitigation - baseline; sign is preserved.", comparison="mitigation-baseline")
    return results or {"delta": _not_estimable("rq7_matched_absolute_delta", eligible_n=len(rows), status="NOT_ESTIMABLE", notes="No common metrics across matched pairs.")}


def analyze_rq7(units: Iterable[RQ7Pair | RQ7Observation], *, seed: int = 20260818, iterations: int = BOOTSTRAP_ITERATIONS) -> dict[str, MetricResult]:
    rows = require_controlled(units)
    if not rows:
        return {"delta": _not_estimable("rq7_matched_absolute_delta", eligible_n=0, status="NOT_ESTIMABLE", notes="No comparable baseline/mitigation pairs.")}
    if all(isinstance(row, RQ7Observation) for row in rows):
        return _rq7_observation_analysis(rows, seed=seed, iterations=iterations)  # type: ignore[arg-type]
    if all(isinstance(row, RQ7Pair) for row in rows):
        return _analyze_rq7_preaggregated(rows)  # type: ignore[arg-type]
    raise ValueError("RQ7 analysis cannot mix raw observations and preaggregated pairs")
