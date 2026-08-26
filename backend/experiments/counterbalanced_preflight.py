"""Offline-only design and preflight for a new counterbalanced RQ6 lineage.

This module cannot call a provider or persist scientific runs.  It turns the
canonical human-reference pairs into a deterministic execution manifest for a
future, separately authorized experiment.  The frozen Phase 11 RQ6 result is
intentionally not read, amended, or replaced here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Literal, Mapping

from backend.evaluation.freeze import FrozenPair, canonical_dataset_checksum
from backend.evaluation.prompts import PROMPT_TEMPLATE_VERSION, prompt_hash
from backend.evaluation.planning import PairRecord, SOURCE_FAMILIES
from backend.core.model_registry import MODEL_REGISTRY
from backend.evaluation.pricing import price_for_model
from backend.evaluation.routing import routing_fingerprint, routing_policy_version


DESIGN_IDENTITY = "counterbalanced-source-family-v1"
ANALYSIS_IDENTITY = "counterbalanced-source-family-analysis-v1"
DATASET_SNAPSHOT_ID = "controlled-final-plan-v1"
SEED = 20260818
HUMAN_SELF = "HUMAN_PREFERS_SAME_FAMILY"
HUMAN_OTHER = "HUMAN_PREFERS_OTHER_FAMILY"
FINAL_JUDGES = tuple(MODEL_REGISTRY)


def _digest(*parts: object) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode("utf-8")).hexdigest()


def _family_key(value: str | None) -> str | None:
    return value.lower().replace("_", "-") if isinstance(value, str) and value else None


@dataclass(frozen=True)
class Candidate:
    preference_id: int
    prompt_id: int
    answer_a_id: int
    answer_b_id: int
    answer_a_model: str
    answer_b_model: str
    answer_a_family: str
    answer_b_family: str
    category: str
    judge_name: str
    judge_family: str
    same_family_answer_id: int
    other_family_answer_id: int
    other_family: str
    human_reference_label: Literal["ANSWER_A", "ANSWER_B"]
    human_reference_stratum: Literal["HUMAN_PREFERS_SAME_FAMILY", "HUMAN_PREFERS_OTHER_FAMILY"]
    answer_a_text: str
    answer_b_text: str

    @property
    def selection_key(self) -> str:
        return _digest(DESIGN_IDENTITY, SEED, self.preference_id, self.prompt_id, self.answer_a_id, self.answer_b_id, self.judge_name)


@dataclass(frozen=True)
class ScheduledPass:
    pass_number: Literal[1, 2]
    presentation_order: Literal["AB", "BA"]
    presented_answer_a_id: int
    presented_answer_b_id: int


@dataclass(frozen=True)
class SelectedUnit:
    unit_id: str
    candidate: Candidate
    passes: tuple[ScheduledPass, ScheduledPass]


def _candidate_for(pair: PairRecord, judge_name: str) -> Candidate | None:
    """Return one source-known, human-reference-stratifiable candidate or None."""
    answer_a_family = SOURCE_FAMILIES.get(pair.answer_a_model)
    answer_b_family = SOURCE_FAMILIES.get(pair.answer_b_model)
    judge_family = _family_key(MODEL_REGISTRY[judge_name].family)
    if not all((pair.answer_a_text.strip(), pair.answer_b_text.strip(), answer_a_family, answer_b_family, judge_family)):
        return None
    if pair.human_label not in {"ANSWER_A", "ANSWER_B"} or _family_key(answer_a_family) == _family_key(answer_b_family):
        return None
    answer_a_is_same = _family_key(answer_a_family) == judge_family
    answer_b_is_same = _family_key(answer_b_family) == judge_family
    if answer_a_is_same == answer_b_is_same:
        return None
    same_id, other_id = (pair.answer_a_id, pair.answer_b_id) if answer_a_is_same else (pair.answer_b_id, pair.answer_a_id)
    human_prefers_same = (pair.human_label == "ANSWER_A") == answer_a_is_same
    return Candidate(
        preference_id=pair.preference_id, prompt_id=pair.prompt_id, answer_a_id=pair.answer_a_id, answer_b_id=pair.answer_b_id,
        answer_a_model=pair.answer_a_model, answer_b_model=pair.answer_b_model, answer_a_family=answer_a_family, answer_b_family=answer_b_family,
        category=pair.category, judge_name=judge_name, judge_family=answer_a_family if answer_a_is_same else answer_b_family,
        same_family_answer_id=same_id, other_family_answer_id=other_id,
        other_family=answer_b_family if answer_a_is_same else answer_a_family,
        human_reference_label=pair.human_label,
        human_reference_stratum=HUMAN_SELF if human_prefers_same else HUMAN_OTHER,
        answer_a_text=pair.answer_a_text, answer_b_text=pair.answer_b_text,
    )


def candidate_population(pairs: Iterable[PairRecord]) -> tuple[list[Candidate], dict[str, object]]:
    """Audit all available source-known candidates without sampling or mutation."""
    candidates = [candidate for pair in pairs for judge in FINAL_JUDGES if (candidate := _candidate_for(pair, judge)) is not None]
    def counted(key):
        values = Counter(key(row) for row in candidates)
        return [{"stratum": list(name) if isinstance(name, tuple) else name, "count": count} for name, count in sorted(values.items(), key=lambda item: str(item[0]))]
    return candidates, {
        "unique_pairs_with_at_least_one_candidate": len({candidate.preference_id for candidate in candidates}) if candidates else 0,
        "eligible_judge_pair_candidates": len(candidates),
        "per_judge": counted(lambda row: row.judge_name),
        "per_source_family_pairing": counted(lambda row: (row.judge_name, row.judge_family, row.other_family)),
        "per_category": counted(lambda row: (row.judge_name, row.category)),
        "per_human_reference_outcome": counted(lambda row: (row.judge_name, row.human_reference_stratum)),
        "configured_judges_without_candidates": [judge for judge in FINAL_JUDGES if not any(row.judge_name == judge for row in candidates)],
    }


def select_balanced_units(candidates: Iterable[Candidate]) -> list[SelectedUnit]:
    """Exact-match human-reference strata within judge × other-family × category."""
    grouped: dict[tuple[str, str, str], dict[str, list[Candidate]]] = defaultdict(lambda: defaultdict(list))
    for candidate in candidates:
        grouped[(candidate.judge_name, candidate.other_family, candidate.category)][candidate.human_reference_stratum].append(candidate)
    selected: list[SelectedUnit] = []
    for key in sorted(grouped):
        strata = grouped[key]
        n = min(len(strata[HUMAN_SELF]), len(strata[HUMAN_OTHER]))
        for candidate in sorted(strata[HUMAN_SELF], key=lambda row: row.selection_key)[:n] + sorted(strata[HUMAN_OTHER], key=lambda row: row.selection_key)[:n]:
            unit_id = _digest(DESIGN_IDENTITY, candidate.selection_key)
            selected.append(SelectedUnit(
                unit_id=unit_id,
                candidate=candidate,
                passes=(
                    ScheduledPass(1, "AB", candidate.answer_a_id, candidate.answer_b_id),
                    ScheduledPass(2, "BA", candidate.answer_b_id, candidate.answer_a_id),
                ),
            ))
    return sorted(selected, key=lambda unit: unit.unit_id)


def validate_design(units: Iterable[SelectedUnit]) -> dict[str, object]:
    """Provider-free hard gates.  Any error makes the design ineligible for execution."""
    rows = list(units)
    errors: list[str] = []
    if len({row.unit_id for row in rows}) != len(rows):
        errors.append("duplicate_unit_id")
    if len({(row.candidate.preference_id, row.candidate.judge_name) for row in rows}) != len(rows):
        errors.append("duplicate_pair_judge_unit")
    presentation = Counter()
    human_by_judge: dict[str, Counter[str]] = defaultdict(Counter)
    human_by_match_stratum: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
    for unit in rows:
        candidate = unit.candidate
        if candidate.same_family_answer_id == candidate.other_family_answer_id:
            errors.append(f"invalid_source_mapping:{unit.unit_id}")
        if len(unit.passes) != 2 or {item.presentation_order for item in unit.passes} != {"AB", "BA"}:
            errors.append(f"missing_ab_ba_schedule:{unit.unit_id}")
            continue
        first, second = unit.passes
        if (first.presented_answer_a_id, first.presented_answer_b_id) != (candidate.answer_a_id, candidate.answer_b_id) or (second.presented_answer_a_id, second.presented_answer_b_id) != (candidate.answer_b_id, candidate.answer_a_id):
            errors.append(f"irreversible_original_answer_mapping:{unit.unit_id}")
        for scheduled in unit.passes:
            presentation["same_in_A" if scheduled.presented_answer_a_id == candidate.same_family_answer_id else "same_in_B" if scheduled.presented_answer_b_id == candidate.same_family_answer_id else "same_missing"] += 1
        human_by_judge[candidate.judge_name][candidate.human_reference_stratum] += 1
        human_by_match_stratum[(candidate.judge_name, candidate.other_family, candidate.category)][candidate.human_reference_stratum] += 1
    if presentation["same_missing"]:
        errors.append("same_family_answer_missing_from_presentation")
    if presentation["same_in_A"] != presentation["same_in_B"]:
        errors.append("presentation_not_exactly_counterbalanced")
    for judge, counts in human_by_judge.items():
        if counts[HUMAN_SELF] != counts[HUMAN_OTHER]:
            errors.append(f"human_reference_unbalanced:{judge}")
    for stratum, counts in human_by_match_stratum.items():
        if counts[HUMAN_SELF] != counts[HUMAN_OTHER]:
            errors.append("matched_stratum_unbalanced:" + "|".join(stratum))
    return {
        "ok": not errors,
        "errors": sorted(set(errors)),
        "selected_units": len(rows),
        "planned_pass_slots": len(rows) * 2,
        "presentation_proof": {"same_family_in_A": presentation["same_in_A"], "same_family_in_B": presentation["same_in_B"]},
        "human_reference_balance_by_judge": {judge: dict(sorted(counts.items())) for judge, counts in sorted(human_by_judge.items())},
        "balanced_matching_strata": len(human_by_match_stratum),
        "all_matching_strata_exactly_balanced": not any(
            counts[HUMAN_SELF] != counts[HUMAN_OTHER]
            for counts in human_by_match_stratum.values()
        ),
    }


def _dataset_checksum(pairs: Iterable[PairRecord]) -> str:
    return canonical_dataset_checksum([FrozenPair(pair.preference_id, pair.prompt_id, pair.answer_a_id, pair.answer_b_id, pair.answer_a_text, pair.answer_b_text, pair.answer_a_model, pair.answer_b_model, pair.category, pair.human_label) for pair in pairs])


def _token_estimate(text: str) -> int:
    return (len(text) + 3) // 4


def cost_preflight(units: Iterable[SelectedUnit], prompt_text_by_id: Mapping[int, str]) -> dict[str, object]:
    """Use the same conservative character-based reservation rule as real execution."""
    by_judge: dict[str, dict[str, Decimal | int | str]] = {}
    for unit in units:
        judge = unit.candidate.judge_name
        row = by_judge.setdefault(judge, {"planned_calls": 0, "input_tokens": 0, "output_tokens": 0, "usd": Decimal("0")})
        candidate = unit.candidate
        input_tokens = _token_estimate(prompt_text_by_id.get(candidate.prompt_id, "") + candidate.answer_a_text + candidate.answer_b_text + " " * 600)
        output_tokens = MODEL_REGISTRY[judge].max_output_tokens
        rate = price_for_model(judge)
        calls = len(unit.passes)
        row["planned_calls"] = int(row["planned_calls"]) + calls
        row["input_tokens"] = int(row["input_tokens"]) + input_tokens * calls
        row["output_tokens"] = int(row["output_tokens"]) + output_tokens * calls
        row["usd"] = Decimal(row["usd"]) + calls * (Decimal(input_tokens) * rate.input_per_token + Decimal(output_tokens) * rate.output_per_token)
    total = {"planned_calls": 0, "input_tokens": 0, "output_tokens": 0, "usd": Decimal("0")}
    serialized: dict[str, object] = {}
    for judge, row in sorted(by_judge.items()):
        total["planned_calls"] += int(row["planned_calls"]); total["input_tokens"] += int(row["input_tokens"]); total["output_tokens"] += int(row["output_tokens"]); total["usd"] += Decimal(row["usd"])
        serialized[judge] = {**row, "provider": MODEL_REGISTRY[judge].provider.value, "estimated_usd": str(Decimal(row["usd"]).quantize(Decimal("0.000001")))}
        del serialized[judge]["usd"]
    return {"pricing_version": "pricing-config-v1", "per_judge": serialized, "total": {"planned_calls": total["planned_calls"], "input_tokens": total["input_tokens"], "output_tokens": total["output_tokens"], "estimated_usd": str(total["usd"].quantize(Decimal("0.000001")))}, "recommended_hard_cap_usd": str((total["usd"] * Decimal("1.20")).quantize(Decimal("0.01")))}


def conditional_precision_benchmark(units: Iterable[SelectedUnit]) -> dict[str, object]:
    """Report a transparent planning precision benchmark, not a power claim."""
    counts = Counter(unit.candidate.judge_name for unit in units)

    def half_width(count: int) -> float | None:
        # Largest normal-approximation 95% half-width occurs at p=0.5.
        return 1.96 * math.sqrt(0.25 / count) if count else None

    return {
        "condition": "If every selected logical unit yields a stable decisive outcome.",
        "measure": "Maximum normal-approximation 95% half-width at p=0.5, expressed in percentage points.",
        "overall_units": sum(counts.values()),
        "overall_half_width_pp": round(100 * half_width(sum(counts.values())), 2) if counts else None,
        "by_judge": {
            judge: {"units": count, "half_width_pp": round(100 * half_width(count), 2)}
            for judge, count in sorted(counts.items())
        },
        "caveat": "Actual precision will be weaker if stable decisive coverage is below 100%; this is not a minimum detectable effect or a power guarantee.",
    }


def operational_coverage_proxy(session) -> dict[str, object]:
    """Read prior controlled pass outcomes only to size an operational reserve.

    This is not an RQ6 outcome estimate and does not use the invalid frozen RQ6
    estimator.  It is deliberately limited to provider/parse completion rates.
    """
    from backend.core.controlled_models import ControlledRun, RunPass
    from backend.evaluation.persistence import EvidenceClass

    run_ids = [row.id for row in session.query(ControlledRun.id).filter(
        ControlledRun.metadata_json["evidence_class"].as_string() == EvidenceClass.CONTROLLED.value
    ).all()]
    outcomes = Counter(row.outcome for row in session.query(RunPass.outcome).filter(RunPass.run_id.in_(run_ids)).all()) if run_ids else Counter()
    total = sum(outcomes.values())
    semantic = sum(outcomes[outcome] for outcome in {"ANSWER_A", "ANSWER_B", "TIE", "UNKNOWN"})
    pass_rate = semantic / total if total else None
    return {
        "source": "Existing CONTROLLED pass outcome ledger; operational sizing only.",
        "total_observed_passes": total,
        "semantic_response_passes": semantic,
        "semantic_response_rate": pass_rate,
        "expected_complete_two_pass_operational_coverage": pass_rate * pass_rate if pass_rate is not None else None,
        "assumption": "Independent pass-level operational failures. This is not expected stable decisive coverage and is not used to infer source-family preference.",
    }


def materialize(pairs: Iterable[PairRecord], prompt_text_by_id: Mapping[int, str], *, operational_proxy: Mapping[str, object] | None = None) -> dict[str, object]:
    pair_rows = list(pairs)
    candidates, population = candidate_population(pair_rows)
    population["canonical_pair_population"] = len(pair_rows)
    units = select_balanced_units(candidates)
    validation = validate_design(units)
    if not validation["ok"]:
        raise ValueError("offline RQ6 design validation failed: " + ", ".join(validation["errors"]))
    manifest = {
        "design_identity": DESIGN_IDENTITY,
        "analysis_identity": ANALYSIS_IDENTITY,
        "rq_code": "RQ6_REMEDIATION",
        "scientific_question": "When one answer comes from the judge's own model family and the competing answer comes from another family, is there evidence of matched source-family preference after presentation order is explicitly counterbalanced?",
        "dataset_snapshot_id": DATASET_SNAPSHOT_ID,
        "dataset_checksum": _dataset_checksum(pair_rows),
        "sampling_seed": SEED,
        "prompt_template_version": PROMPT_TEMPLATE_VERSION,
        "prompt_template_sha256": prompt_hash(),
        "source_identity_blinded_to_judge": True,
        "routing_policy_version": routing_policy_version(),
        "routing_fingerprint": routing_fingerprint(),
        "configured_final_judges": list(FINAL_JUDGES),
        "included_judges": sorted({unit.candidate.judge_name for unit in units}),
        "excluded_configured_judges": {judge: "No source-known candidate contains an answer from this judge family." for judge in FINAL_JUDGES if not any(unit.candidate.judge_name == judge for unit in units)},
        "eligibility_policy": "Nonempty answer texts; known source families; exactly one answer matches the judge family; definitive canonical human preference reference label; no inference from answer text.",
        "balancing_policy": "Exact balance of HUMAN_PREFERS_SAME_FAMILY and HUMAN_PREFERS_OTHER_FAMILY within judge × competing source family × prompt category, selected by stable SHA-256 order.",
        "presentation_policy": "Every logical unit has exactly AB and BA passes; all outcomes are mapped back to immutable original answer IDs and source families.",
        "primary_estimand": "Stable same-family preference rate among valid stable decisive pairs; a stable same-family outcome requires both mapped AB and BA passes to choose the same-family original answer.",
        "secondary_metrics": ["stable other-family preference rate", "order-sensitive disagreement rate", "valid decisive coverage", "tie/abstention rate", "human-reference agreement within each human-reference stratum", "difference between human-reference-stratum agreement rates", "equal-weight judge macro-average"],
        "outcome_policy": "Ties/abstentions, invalid responses, operational failures, and AB/BA disagreement remain explicit reported outcome classes and are never silently discarded. Coverage denominator is all selected units.",
        "inference_plan": {"unit": "logical experimental unit", "bootstrap": "percentile bootstrap at unit level", "seed": SEED, "resamples": 10000, "confidence_interval": "95%", "hypothesis_test": "No 50/50 test is preregistered because source/content quality confounding remains."},
        "interpretation_limit": "This design removes presentation-position confounding but does not establish causal self-preference bias or remove source/content quality confounding.",
        "lineage_policy": "New independent manifest/run/analysis lineage. It does not amend, reuse outcomes from, or replace frozen Phase 11 RQ6 evidence.",
        "candidate_population": population,
        "validation": validation,
        "conditional_precision_benchmark": conditional_precision_benchmark(units),
        "operational_coverage_proxy": dict(operational_proxy) if operational_proxy is not None else None,
        "cost_preflight": cost_preflight(units, prompt_text_by_id),
        "units": [{"unit_id": unit.unit_id, "preference_id": unit.candidate.preference_id, "prompt_id": unit.candidate.prompt_id, "original_answer_ids": [unit.candidate.answer_a_id, unit.candidate.answer_b_id], "judge_name": unit.candidate.judge_name, "judge_family": unit.candidate.judge_family, "source_family_mapping": {str(unit.candidate.answer_a_id): unit.candidate.answer_a_family, str(unit.candidate.answer_b_id): unit.candidate.answer_b_family}, "same_family_answer_id": unit.candidate.same_family_answer_id, "other_family_answer_id": unit.candidate.other_family_answer_id, "other_family": unit.candidate.other_family, "category": unit.candidate.category, "human_reference_label": unit.candidate.human_reference_label, "human_reference_stratum": unit.candidate.human_reference_stratum, "passes": [asdict(item) for item in unit.passes]} for unit in units],
    }
    digest_body = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    manifest["manifest_sha256"] = hashlib.sha256(digest_body.encode("utf-8")).hexdigest()
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize the offline-only counterbalanced RQ6 preflight manifest.")
    parser.add_argument("--output", type=Path, required=True, help="New non-Phase-11 JSON manifest path.")
    args = parser.parse_args()
    from backend.core.database import SessionLocal
    from backend.evaluation.planning import database_pairs
    from backend.core.models import Prompt
    with SessionLocal() as session:
        pairs = database_pairs(session)
        prompt_text = dict(session.query(Prompt.id, Prompt.text).all())
        proxy = operational_coverage_proxy(session)
    manifest = materialize(pairs, prompt_text, operational_proxy=proxy)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"design_identity": manifest["design_identity"], "selected_units": manifest["validation"]["selected_units"], "planned_pass_slots": manifest["validation"]["planned_pass_slots"], "manifest_sha256": manifest["manifest_sha256"], "estimated_usd": manifest["cost_preflight"]["total"]["estimated_usd"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
