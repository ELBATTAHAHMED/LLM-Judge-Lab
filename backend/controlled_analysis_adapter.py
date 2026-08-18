"""Controlled run/pass → authoritative Phase 4 input adapters.

This is the sole bridge from persisted controlled evidence to the analysis
layer. It intentionally has no legacy-table query and rejects non-controlled
runs before a scientific metric is constructed.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

from controlled_models import ControlledRun, ExperimentalUnit, RunPass
from phase4_metrics import RQ1Unit, RQ2Repetition, RQ3Pair, RQ6Unit, RQ7Observation, VariantPair


def pass_outcome(record: RunPass) -> str:
    if record.outcome:
        return record.outcome
    if record.raw_verdict in {"ANSWER_A", "ANSWER_B", "TIE", "UNKNOWN"}: return record.raw_verdict
    return {"INVALID": "INVALID_RESPONSE", "PROVIDER_ERROR": "API_ERROR", "TIMEOUT": "TIMEOUT", "REFUSAL": "REFUSAL"}.get(record.parse_status, "INVALID_RESPONSE")


def _verify(run: ControlledRun, unit: ExperimentalUnit) -> None:
    metadata = run.metadata_json or {}
    if metadata.get("evidence_class") != "CONTROLLED" or run.experimental_unit_id != unit.id or metadata.get("controlled_unit_id") != str(unit.id):
        raise ValueError("Run is not controlled evidence linked to the supplied experimental unit")


def rq1_from_run(run: ControlledRun, unit: ExperimentalUnit) -> RQ1Unit:
    _verify(run, unit)
    label = pass_outcome(sorted(run.passes, key=lambda p: p.pass_number)[0]) if run.passes else None
    return RQ1Unit("CONTROLLED", str(unit.id), "RQ1", run.judge_name, unit.condition_code, unit.human_label, label, unit.prompt_category)


def rq2_from_run(run: ControlledRun, unit: ExperimentalUnit, *, group_key: str | None = None, seed_policy: str) -> RQ2Repetition:
    _verify(run, unit)
    first = sorted(run.passes, key=lambda p: p.pass_number)[0] if run.passes else None
    label = pass_outcome(first) if first else None
    route = (first.route_provenance_json if first else None) or {}
    identity = {"pairing_key": unit.pairing_key, "judge": run.judge_name, "provider": run.provider, "requested_model": run.requested_model, "effective_model": (first.effective_model if first else run.effective_model), "configured_upstream": route.get("configured_upstream_provider"), "observed_upstream": route.get("observed_upstream_provider"), "routing_policy_version": route.get("routing_policy_version"), "routing_fingerprint": route.get("routing_fingerprint"), "prompt": run.prompt_template_version, "temperature": float(unit.temperature or 0), "top_p": float(run.top_p) if run.top_p is not None else None, "seed_policy": seed_policy, "condition": unit.condition_code}
    exact_key = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return RQ2Repetition("CONTROLLED", str(unit.id), "RQ2", run.judge_name, unit.condition_code, group_key or exact_key, unit.answer_a_id, unit.answer_b_id, float(unit.temperature or 0), unit.repetition_index, run.retry_count, label, run.provider, run.requested_model, run.prompt_template_version or "NOT_RECORDED", float(run.top_p) if run.top_p is not None else None, seed_policy, first.effective_model if first and first.effective_model else "NOT_RECORDED", route.get("configured_upstream_provider"), route.get("observed_upstream_provider"), route.get("routing_policy_version"), route.get("routing_fingerprint"))


def _variant_from_run(run: ControlledRun, unit: ExperimentalUnit, *, rq_code: str) -> VariantPair:
    """Map physical passes through persisted variant-slot provenance."""
    _verify(run, unit)
    records = sorted(run.passes, key=lambda p: p.pass_number)
    outcomes: list[str | None] = []
    valid = bool(unit.counterfactual_variant_id)
    for record in records:
        value = pass_outcome(record)
        slots = (record.presentation_provenance_json or {}).get("variant_slot")
        if not valid or slots not in {"A", "B"}:
            valid = False; continue
        if value == "TIE": outcomes.append("TIE")
        elif value == "ANSWER_A": outcomes.append("VARIANT" if slots == "A" else "ORIGINAL")
        elif value == "ANSWER_B": outcomes.append("VARIANT" if slots == "B" else "ORIGINAL")
        else: outcomes.append(None)
    # A paired control is eligible only if both mapped presentations agree or
    # are both tie; disagreement remains an explicit execution exclusion.
    mapped = outcomes[0] if outcomes and all(value == outcomes[0] for value in outcomes) else None
    return VariantPair("CONTROLLED", str(unit.id), rq_code, run.judge_name, unit.condition_code, valid and mapped is not None, mapped, unit.presentation_order)


def rq4_from_run(run: ControlledRun, unit: ExperimentalUnit) -> VariantPair:
    return _variant_from_run(run, unit, rq_code="RQ4")


def rq5_from_run(run: ControlledRun, unit: ExperimentalUnit) -> VariantPair:
    return _variant_from_run(run, unit, rq_code="RQ5")


def rq7_observations(runs: Iterable[tuple[ControlledRun, ExperimentalUnit]]) -> list[RQ7Observation]:
    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for run, unit in runs:
        _verify(run, unit)
        key = (unit.pairing_key or str(unit.id), run.judge_name); row = grouped.setdefault(key, {"human": unit.human_label})
        mapped = []
        for record in sorted(run.passes, key=lambda p: p.pass_number):
            value = pass_outcome(record)
            if value in {"ANSWER_A", "ANSWER_B"}:
                value = "ANSWER_A" if record.winner_answer_id == unit.answer_a_id else "ANSWER_B" if record.winner_answer_id == unit.answer_b_id else "INVALID_RESPONSE"
            mapped.append(value)
        if unit.condition_code == "BASELINE_STANDARD": row["baseline"] = mapped[0] if mapped else None
        elif unit.condition_code == "DUAL_SWAP":
            row["dual_ab"] = mapped[0] if mapped else None; row["dual_ba"] = mapped[1] if len(mapped) > 1 else None
    return [RQ7Observation("CONTROLLED", f"{key[0]}:{key[1]}", "RQ7", key[1], "MATCHED", key[0], value.get("human"), value.get("baseline"), value.get("dual_ab"), value.get("dual_ba")) for key, value in grouped.items()]


def rq3_from_run(run: ControlledRun, unit: ExperimentalUnit) -> RQ3Pair:
    _verify(run, unit)
    passes = {record.pass_number: record for record in run.passes}
    first, second = passes.get(1), passes.get(2)
    def mapped(record: RunPass | None) -> str | None:
        if record is None: return None
        raw = pass_outcome(record)
        if raw not in {"ANSWER_A", "ANSWER_B"}: return raw
        return "ANSWER_A" if record.winner_answer_id == unit.answer_a_id else "ANSWER_B" if record.winner_answer_id == unit.answer_b_id else "INVALID_RESPONSE"
    return RQ3Pair("CONTROLLED", str(unit.id), "RQ3", run.judge_name, unit.condition_code, mapped(first), mapped(second), int(first is not None and first.winner_answer_id == first.presented_answer_a_id) + int(second is not None and second.winner_answer_id == second.presented_answer_a_id), int(first is not None and first.winner_answer_id == first.presented_answer_b_id) + int(second is not None and second.winner_answer_id == second.presented_answer_b_id))


def rq6_from_run(run: ControlledRun, unit: ExperimentalUnit) -> RQ6Unit:
    _verify(run, unit)
    source = {"gpt-4": "openai", "gpt-3.5-turbo": "openai", "claude-v1": "anthropic", "llama-13b": "meta-llama"}
    judge_family = {"gpt-4o-mini": "openai", "anthropic/claude-3-haiku": "anthropic", "meta-llama/llama-3.3-70b-instruct": "meta-llama"}.get(run.judge_name)
    answer_families = {unit.answer_a_id: source.get(unit.answer_a_author_id or ""), unit.answer_b_id: source.get(unit.answer_b_author_id or "")}
    winner = run.final_winner_answer_id
    if run.final_result_type == "TIE": outcome = "TIE"
    elif winner is None or answer_families.get(winner) is None: outcome = None
    else: outcome = "SELF" if answer_families[winner] == judge_family else "OTHER"
    return RQ6Unit("CONTROLLED", str(unit.id), "RQ6", run.judge_name, unit.condition_code, all(answer_families.values()), outcome, "A" if unit.presentation_order == "SELF_A" else "B" if unit.presentation_order == "SELF_B" else None)


@dataclass(frozen=True)
class ResumeState:
    completed: tuple[str, ...]
    retryable: tuple[str, ...]
    non_retryable: tuple[str, ...]
    pending: tuple[str, ...]


def resume_state(runs: Iterable[ControlledRun]) -> ResumeState:
    completed: list[str] = []; retryable: list[str] = []; non_retryable: list[str] = []; pending: list[str] = []
    for run in runs:
        key = run.idempotency_key
        if run.status == "SUCCEEDED": completed.append(key)
        elif run.status in {"PENDING", "RUNNING", "PARTIAL"}: pending.append(key)
        elif run.error_code in {"TIMEOUT", "PROVIDER_ERROR"}: retryable.append(key)
        else: non_retryable.append(key)
    return ResumeState(tuple(completed), tuple(retryable), tuple(non_retryable), tuple(pending))
