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
    return {"tie_count": values.count("TIE"), "unknown_count": values.count("UNKNOWN"), "invalid_count": values.count("INVALID_RESPONSE"), "failure_count": sum(v in {"API_ERROR", "TIMEOUT", "REFUSAL", "AMBIGUOUS"} for v in values), "missing_count": sum(v is None or v == "MISSING_PASS" for v in values)}


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


def analyze_rq2(units: Iterable[RQ2Repetition], *, seed: int = 20260818, iterations: int = BOOTSTRAP_ITERATIONS) -> dict[str, MetricResult]:
    rows = require_controlled(units); groups = defaultdict(list)
    for row in rows: groups[row.group_key].append(row)
    group_values: list[float] = []; labels = [r.verdict for r in rows]; excluded = 0
    for group in groups.values():
        identity = {(r.answer_a_id, r.answer_b_id, r.judge_name, r.provider, r.requested_model, r.condition, r.temperature, r.prompt_template_version, r.top_p, r.seed_policy) for r in group}
        repetitions = {r.repetition_index for r in group}; valid = [r.verdict for r in group if r.verdict in VALID]
        if len(identity) != 1 or len(repetitions) != len(group) or not valid: excluded += 1; continue
        group_values.append(max(Counter(valid).values()) / len(valid))
    if not group_values: return {"consistency": _not_estimable("rq2_within_unit_consistency", eligible_n=len(groups), status="INSUFFICIENT_ELIGIBLE_UNITS", notes="No complete repeated groups with valid outcomes.", labels=labels)}
    value = mean(group_values); low, high = bootstrap_ci(group_values, lambda xs: mean(xs), seed=seed, iterations=iterations)
    return {"consistency": MetricResult("rq2_within_unit_consistency", value, None, len(group_values), len(groups), len(group_values), excluded_count=excluded, ci_low=low, ci_high=high, notes="Mean modal-verdict proportion over complete exact configuration groups; bootstrap resamples groups.", analysis_seed=seed, bootstrap_iterations=iterations, **_counts(labels))}


@dataclass(frozen=True)
class RQ3Pair(ControlledEvidence):
    pass_ab: str | None
    pass_ba: str | None
    slot_wins_a: int = 0
    slot_wins_b: int = 0


def analyze_rq3(units: Iterable[RQ3Pair], *, seed: int = 20260818, iterations: int = BOOTSTRAP_ITERATIONS) -> dict[str, MetricResult]:
    rows = require_controlled(units); complete = [u for u in rows if u.pass_ab is not None and u.pass_ba is not None]; decisive = [u for u in complete if u.pass_ab in {"ANSWER_A", "ANSWER_B"} and u.pass_ba in {"ANSWER_A", "ANSWER_B"}]
    labels = [x for u in rows for x in (u.pass_ab, u.pass_ba)]
    flip = _rate("rq3_paired_decisive_flip_rate", decisive, lambda u: u.pass_ab != u.pass_ba, eligible_n=len(rows), labels=labels, seed=seed, iterations=iterations, notes="Denominator: complete pairs with two decisive mapped-original outcomes.")
    broad = [u for u in complete if u.pass_ab in VALID and u.pass_ba in VALID]
    disagreement = _rate("rq3_all_paired_disagreement_rate", broad, lambda u: u.pass_ab != u.pass_ba, eligible_n=len(rows), labels=labels, seed=seed, iterations=iterations, notes="Broader valid-label disagreement; distinct from decisive flip rate.")
    slot_a, slot_b = sum(u.slot_wins_a for u in decisive), sum(u.slot_wins_b for u in decisive); slot = _not_estimable("rq3_slot_win_imbalance", eligible_n=len(rows), status="NO_DECISIVE_SLOT_OUTCOMES", notes="No decisive presented-slot outcomes.", labels=labels) if not slot_a + slot_b else MetricResult("rq3_slot_win_imbalance", abs(slot_a-slot_b)/(slot_a+slot_b), abs(slot_a-slot_b), slot_a+slot_b, len(rows), len(decisive), notes="Absolute presented-slot win difference / decisive presented-slot outcomes; not a flip rate.", **_counts(labels))
    return {"paired_decisive_flip_rate": flip, "all_paired_disagreement_rate": disagreement, "slot_win_imbalance": slot, "incomplete_pairs": MetricResult("rq3_incomplete_pair_count", float(len(rows)-len(complete)), len(rows)-len(complete), len(rows), len(rows), len(rows), notes="Pairs missing either presentation pass.", **_counts(labels))}


@dataclass(frozen=True)
class VariantPair(ControlledEvidence):
    variant_valid: bool
    variant_outcome: Literal["VARIANT", "ORIGINAL", "TIE"] | None
    order: str


def _analyze_variant(rq: str, units: Iterable[VariantPair], *, seed: int, iterations: int) -> dict[str, MetricResult]:
    rows = require_controlled(units); valid = [u for u in rows if u.variant_valid and u.variant_outcome in {"VARIANT", "ORIGINAL", "TIE"}]; labels = [u.variant_outcome for u in rows]
    name = f"{rq.lower()}_controlled_variant_win_rate"
    result = _rate(name, valid, lambda u: u.variant_outcome == "VARIANT", eligible_n=len(rows), labels=labels, seed=seed, iterations=iterations, notes="Validated controlled variant wins / valid controlled variant pairs.")
    return {"variant_win_rate": result, "original_win_rate": _rate(f"{rq.lower()}_original_win_rate", valid, lambda u: u.variant_outcome == "ORIGINAL", eligible_n=len(rows), labels=labels, seed=seed, iterations=iterations, notes="Reported separately from variant wins."), "rejected_variant_count": MetricResult(f"{rq.lower()}_rejected_variant_count", float(sum(not u.variant_valid for u in rows)), sum(not u.variant_valid for u in rows), len(rows), len(rows), len(rows), notes="Deterministically invalid variants are excluded.")}


def analyze_rq4(units: Iterable[VariantPair], *, seed: int = 20260818, iterations: int = BOOTSTRAP_ITERATIONS) -> dict[str, MetricResult]: return _analyze_variant("RQ4", units, seed=seed, iterations=iterations)
def analyze_rq5(units: Iterable[VariantPair], *, seed: int = 20260818, iterations: int = BOOTSTRAP_ITERATIONS) -> dict[str, MetricResult]: return _analyze_variant("RQ5", units, seed=seed, iterations=iterations)


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
