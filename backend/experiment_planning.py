"""Deterministic, disabled execution planning for Phase 3."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from model_registry import MODEL_REGISTRY
from models import Answer, HumanPreference, Prompt
from experiment_protocols import PLANNED_BASE_UNIT_LIMIT, PROTOCOLS, get_protocol
from controlled_transforms import checksum, make_format_variant, make_verbosity_variant, validate_format_variant, validate_verbosity_variant
from controlled_freeze import FrozenPair, freeze_reference_pairs
from routing_policy import routing_fingerprint, routing_policy_version


SOURCE_FAMILIES = {"gpt-3.5-turbo": "OPENAI", "gpt-4": "OPENAI", "claude-v1": "ANTHROPIC", "llama-13b": "META_LLAMA", "alpaca-13b": "ALPACA", "vicuna-13b": "VICUNA"}
JUDGE_FAMILIES = {"gpt-4o-mini": "OPENAI", "anthropic/claude-3-haiku": "ANTHROPIC", "meta-llama/llama-3.3-70b-instruct": "META_LLAMA"}
VALID_HUMAN = {"ANSWER_A", "ANSWER_B", "TIE"}


@dataclass(frozen=True)
class PairRecord:
    preference_id: int; prompt_id: int; answer_a_id: int; answer_b_id: int; answer_a_text: str; answer_b_text: str; answer_a_model: str; answer_b_model: str; category: str; human_label: str | None
    @property
    def pair_key(self) -> str: return _digest("pair", self.prompt_id, self.answer_a_id, self.answer_b_id)


@dataclass(frozen=True)
class PlannedUnit:
    unit_id: str; rq_code: str; base_pair_key: str; prompt_id: int; answer_a_id: int; answer_b_id: int; judge_name: str; provider: str; requested_model: str; condition: str; presentation_order: str; repetition_index: int; pass_count: int; temperature: float; variant_checksum: str | None = None
    @property
    def calls(self) -> int: return self.pass_count


def _digest(*parts: object) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()


def human_label(pair: PairRecord) -> str | None:
    if pair.human_label in VALID_HUMAN: return pair.human_label
    return None


def database_pairs(session: Session, *, apply_reference_policy: bool = True) -> list[PairRecord]:
    # The two Answer joins need explicit aliases to remain portable.
    from sqlalchemy.orm import aliased
    answer_a, answer_b = aliased(Answer), aliased(Answer)
    stmt = select(HumanPreference, Prompt, answer_a, answer_b).join(Prompt, HumanPreference.prompt_id == Prompt.id).join(answer_a, HumanPreference.answer_a_id == answer_a.id).join(answer_b, HumanPreference.answer_b_id == answer_b.id).order_by(HumanPreference.id)
    records = []
    for pref, prompt, a, b in session.execute(stmt):
        label = "TIE" if pref.winner_id is None else "ANSWER_A" if pref.winner_id == a.id else "ANSWER_B" if pref.winner_id == b.id else None
        records.append(PairRecord(pref.id, prompt.id, a.id, b.id, a.text, b.text, a.model_name, b.model_name, prompt.category, label))
    if not apply_reference_policy:
        return records
    frozen, _ = freeze_reference_pairs([FrozenPair(r.preference_id, r.prompt_id, r.answer_a_id, r.answer_b_id, r.answer_a_text, r.answer_b_text, r.answer_a_model, r.answer_b_model, r.category, r.human_label) for r in records])
    return [PairRecord(row.preference_id, row.prompt_id, row.answer_a_id, row.answer_b_id, row.answer_a_text, row.answer_b_text, row.answer_a_model, row.answer_b_model, row.category, row.human_label) for row in frozen]


def _eligible(pair: PairRecord, rq_code: str, judge_name: str | None = None) -> bool:
    if rq_code in {"RQ1", "RQ7"}: return bool(pair.answer_a_text.strip() and pair.answer_b_text.strip()) and human_label(pair) is not None
    if rq_code in {"RQ2", "RQ3"}: return bool(pair.answer_a_text.strip() and pair.answer_b_text.strip())
    if rq_code == "RQ4":
        return bool(pair.answer_a_text.strip()) and validate_verbosity_variant(pair.answer_a_id, pair.answer_a_text, make_verbosity_variant(pair.answer_a_text)).valid
    if rq_code == "RQ5":
        return bool(pair.answer_a_text.strip()) and validate_format_variant(pair.answer_a_id, pair.answer_a_text, make_format_variant(pair.answer_a_text)).valid
    if rq_code == "RQ6":
        family = JUDGE_FAMILIES.get(judge_name or "")
        return (
            bool(pair.answer_a_text.strip() and pair.answer_b_text.strip())
            and family is not None
            and {SOURCE_FAMILIES.get(pair.answer_a_model), SOURCE_FAMILIES.get(pair.answer_b_model)}.__contains__(family)
            and SOURCE_FAMILIES.get(pair.answer_a_model) != SOURCE_FAMILIES.get(pair.answer_b_model)
        )
    raise ValueError(rq_code)


def eligibility_audit(pairs: Iterable[PairRecord]) -> dict[str, dict[str, int]]:
    rows = list(pairs); output = {}
    for rq, protocol in PROTOCOLS.items():
        if rq == "RQ6":
            eligible = sum(_eligible(pair, rq, judge) for pair in rows for judge in protocol.judges)
            output[rq] = {"available_pairs": len(rows), "eligible_judge_pair_units": eligible, "excluded": len(rows) * len(protocol.judges) - eligible}
        else:
            eligible = sum(_eligible(pair, rq) for pair in rows)
            output[rq] = {"available_pairs": len(rows), "eligible_base_pairs": eligible, "excluded": len(rows) - eligible}
    return output


def generate_units(pairs: Iterable[PairRecord], rq_code: str, *, limit: int = PLANNED_BASE_UNIT_LIMIT, snapshot_id: str = "unfrozen-local-snapshot") -> list[PlannedUnit]:
    protocol = get_protocol(rq_code); all_pairs = list(pairs); units: list[PlannedUnit] = []
    for judge in protocol.judges:
        eligible = [p for p in all_pairs if _eligible(p, rq_code, judge if rq_code == "RQ6" else None)]
        selected = sorted(eligible, key=lambda p: _digest(snapshot_id, rq_code, judge, p.pair_key))[:limit]
        for pair_index, pair in enumerate(selected):
            conditions = protocol.conditions; temperatures = protocol.temperatures if rq_code == "RQ2" else (0.0,)
            for condition, temperature in zip(conditions, temperatures) if rq_code == "RQ2" else ((condition, temperature) for condition in conditions for temperature in temperatures):
                reps = range(protocol.repetitions)
                for rep in reps:
                    order = "AB"
                    variant_checksum = None
                    if rq_code in {"RQ3", "RQ4", "RQ5"}: order = "AB_BA"
                    if rq_code == "RQ6":
                        # Stable sorted selection plus alternation guarantees at
                        # most one-unit slot imbalance for each judge allocation.
                        order = "SELF_A" if pair_index % 2 == 0 else "SELF_B"
                    if rq_code == "RQ4": variant_checksum = checksum(make_verbosity_variant(pair.answer_a_text))
                    if rq_code == "RQ5": variant_checksum = checksum(make_format_variant(pair.answer_a_text))
                    provider = MODEL_REGISTRY[judge].provider.value
                    unit_id = _digest(protocol.protocol_version, snapshot_id, routing_policy_version(), routing_fingerprint(), rq_code, pair.pair_key, judge, condition, order, rep, temperature, variant_checksum)
                    passes = 2 if rq_code == "RQ7" and condition == "DUAL_SWAP" else protocol.pass_count
                    units.append(PlannedUnit(unit_id, rq_code, pair.pair_key, pair.prompt_id, pair.answer_a_id, pair.answer_b_id, judge, provider, judge, condition, order, rep, passes, temperature, variant_checksum))
    return units


def validate_units(units: Iterable[PlannedUnit]) -> list[str]:
    rows = list(units); errors = []; ids = [u.unit_id for u in rows]
    if len(ids) != len(set(ids)): errors.append("duplicate_unit_id")
    for unit in rows:
        if unit.answer_a_id <= 0 or unit.answer_b_id <= 0 or unit.answer_a_id == unit.answer_b_id: errors.append(f"invalid_answer_identity:{unit.unit_id}")
        if unit.judge_name not in MODEL_REGISTRY or unit.provider != MODEL_REGISTRY[unit.judge_name].provider.value: errors.append(f"inconsistent_model_allocation:{unit.unit_id}")
        if unit.repetition_index < 0 or unit.pass_count < 1 or not unit.condition: errors.append(f"missing_or_invalid_configuration:{unit.unit_id}")
        if unit.rq_code in {"RQ4", "RQ5"} and not unit.variant_checksum: errors.append(f"invalid_variant_linkage:{unit.unit_id}")
        if unit.rq_code in {"RQ3", "RQ4", "RQ5"} and (unit.presentation_order != "AB_BA" or unit.pass_count != 2): errors.append(f"incomplete_swap_pair:{unit.unit_id}")
        if unit.rq_code == "RQ7" and unit.condition == "DUAL_SWAP" and unit.pass_count != 2: errors.append(f"incomplete_mitigation_swap:{unit.unit_id}")
    for judge, group in _group_by(rows, lambda u: u.judge_name).items():
        rq6 = [u for u in group if u.rq_code == "RQ6"]
        if rq6 and abs(sum(u.presentation_order == "SELF_A" for u in rq6) - sum(u.presentation_order == "SELF_B" for u in rq6)) > 1: errors.append(f"unbalanced_rq6_slots:{judge}")
    for key, group in _group_by([u for u in rows if u.rq_code == "RQ7"], lambda u: (u.base_pair_key, u.judge_name)).items():
        if {u.condition for u in group} != {"BASELINE_STANDARD", "DUAL_SWAP"}: errors.append(f"unmatched_rq7_strategy:{key[0]}:{key[1]}")
    return errors


def _group_by(rows: Iterable[PlannedUnit], key):
    groups: dict[object, list[PlannedUnit]] = {}
    for row in rows: groups.setdefault(key(row), []).append(row)
    return groups


def manifest(rq_code: str, units: Iterable[PlannedUnit], snapshot_id: str) -> dict[str, object]:
    rows = list(units); body = {"rq_code": rq_code, "protocol": get_protocol(rq_code).as_dict(), "dataset_snapshot_id": snapshot_id, "provider_execution": "DISABLED_PHASE3", "routing_policy_version": routing_policy_version(), "routing_fingerprint": routing_fingerprint(), "units": [asdict(row) for row in rows]}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")); body["manifest_sha256"] = checksum(canonical)
    return body


def call_plan(pairs: Iterable[PairRecord], *, limit: int = PLANNED_BASE_UNIT_LIMIT, snapshot_id: str = "unfrozen-local-snapshot") -> dict[str, dict[str, int]]:
    rows = list(pairs)
    return {rq: {"base_or_judge_pair_units": len(units := generate_units(rows, rq, limit=limit, snapshot_id=snapshot_id)), "planned_calls": sum(u.calls for u in units)} for rq in PROTOCOLS}


def execution_is_disabled(*_args, **_kwargs) -> None:
    raise RuntimeError("Phase 3 provides plan/validate only. Provider execution is disabled.")
