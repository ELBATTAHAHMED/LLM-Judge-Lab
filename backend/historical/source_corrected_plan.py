"""Provider-free planner for source-text-corrected controlled reruns.

The only correction authority is the frozen reconciliation artifact.  This
module may validate raw source bytes against that artifact, but never attempts
to rediscover which historical records were affected.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, ROUND_UP
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from backend.historical.source_reconciliation import FrozenRecord, load_raw_source, model_name, sha
from backend.core.controlled_models import DatasetVersion, ExperimentalUnit, Experiment
from backend.evaluation.prompts import PROMPT_TEMPLATE_VERSION, build_messages, prompt_hash
from backend.evaluation.transforms import make_format_variant, make_verbosity_variant
from backend.evaluation.retry_policy import FAILURE_POLICY_VERSION, RETRY_POLICY_VERSION
from backend.core.model_registry import MODEL_REGISTRY, Provider
from backend.core.models import Answer, Prompt
from backend.evaluation.pricing import CONFIG as PRICING_CONFIG, price_for_model
from backend.evaluation.routing import frozen_openrouter_route, routing_fingerprint, routing_policy_version
from backend.historical.source_corrected_models import (SourceCorrectedExecutionAttempt, SourceCorrectedExecutionBatch,
                                               SourceCorrectedExecutionSlot, SourceCorrectedReuseLedger)


ROOT = Path(__file__).resolve().parent.parent.parent
RECONCILIATION_PATH = ROOT / "evidence" / "remediation" / "source_text_reconciliation_v1.json"
MANIFEST_PATH = ROOT / "evidence" / "remediation" / "controlled_source_text_corrected_execution_manifest_v1.json"
REUSE_LEDGER_PATH = ROOT / "evidence" / "remediation" / "controlled_source_text_corrected_reuse_ledger_v1.json"
PREFLIGHT_PATH = ROOT / "evidence" / "remediation" / "controlled_source_text_corrected_preflight_v1.json"
RECONCILIATION_SHA256 = "186b191fe63ac8b9583431c3821b157612d6e7335674079b1c22d7d79092d467"
MANIFEST_IDENTITY = "controlled-source-text-corrected-execution-manifest-v1"
DATASET_VERSION = "controlled-source-text-corrected-v1"
CONFIRMATION = "I_CONFIRM_SOURCE_CORRECTED_PAID_EXECUTION"
JUDGES = tuple(MODEL_REGISTRY)


class SourceCorrectedPreflightError(PermissionError):
    pass


class SourceCorrectedExecutionStore:
    """Durable, fail-closed state transitions for a later authorized runner.

    C2 never invokes a provider.  Reservation is deliberately separate from
    ``mark_sent`` so a process crash cannot be mistaken for a completed call.
    """
    TERMINAL = {"COMPLETED", "FAILED", "AMBIGUOUS"}

    def reserve(self, session: Session, batch_id: Any, planned_pass_id: str, *, owner: str) -> SourceCorrectedExecutionAttempt:
        batch = session.scalar(select(SourceCorrectedExecutionBatch).where(SourceCorrectedExecutionBatch.id == batch_id).with_for_update())
        slot = session.scalar(select(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == batch_id, SourceCorrectedExecutionSlot.planned_pass_id == planned_pass_id).with_for_update())
        if batch is None or slot is None or slot.state != "PENDING" or batch.status not in {"MATERIALIZED", "RUNNING"}:
            raise SourceCorrectedPreflightError("slot is not safely reservable")
        caps = {key: Decimal(value) for key, value in batch.provider_hard_caps_json.items()}
        reserved = sum((Decimal(row.reserved_usd) for row in session.scalars(select(SourceCorrectedExecutionAttempt).join(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == batch_id))), Decimal("0"))
        forecast = Decimal(slot.estimated_input_tokens) * price_for_model(slot.judge_id).input_per_token + Decimal(slot.estimated_output_tokens) * price_for_model(slot.judge_id).output_per_token
        provider_reserved = sum((Decimal(row.reserved_usd) for row in session.scalars(select(SourceCorrectedExecutionAttempt).join(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == batch_id, SourceCorrectedExecutionSlot.provider == slot.provider))), Decimal("0"))
        if reserved + forecast > Decimal(batch.global_hard_cap_usd) or provider_reserved + forecast > caps[slot.provider]:
            raise SourceCorrectedPreflightError("budget guard stopped execution before provider transport")
        index = slot.attempt_count; attempt = SourceCorrectedExecutionAttempt(slot_id=slot.id, attempt_id=stable_sha({"planned_pass_id": planned_pass_id, "attempt": index}), attempt_index=index, state="RESERVED", reserved_usd=forecast, details_json={"owner": owner, "provider_transport": "NOT_SENT"})
        slot.state, slot.attempt_count, slot.execution_owner, slot.reserved_usd = "RESERVED", index + 1, owner, forecast; batch.status = "RUNNING"; session.add(attempt); session.flush()
        return attempt

    @staticmethod
    def mark_sent(session: Session, attempt: SourceCorrectedExecutionAttempt, *, owner: str) -> None:
        slot = session.get(SourceCorrectedExecutionSlot, attempt.slot_id)
        if slot is None or slot.state != "RESERVED" or slot.execution_owner != owner or attempt.state != "RESERVED":
            raise SourceCorrectedPreflightError("cannot mark an unreserved slot sent")
        slot.state, attempt.state = "SENT", "SENT"; session.flush()

    @staticmethod
    def recover_crash(session: Session, batch_id: Any) -> None:
        """A sent request without a persisted response fails closed as ambiguous."""
        for slot in session.scalars(select(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == batch_id, SourceCorrectedExecutionSlot.state.in_(("RESERVED", "SENT"))).with_for_update()):
            latest = session.scalar(select(SourceCorrectedExecutionAttempt).where(SourceCorrectedExecutionAttempt.slot_id == slot.id).order_by(SourceCorrectedExecutionAttempt.attempt_index.desc()))
            if slot.state == "RESERVED":
                slot.state = "PENDING"
                if latest is not None: latest.state, latest.retry_decision = "ABORTED_BEFORE_TRANSPORT", "RETRY"
            else:
                slot.state = "AMBIGUOUS"
                if latest is not None: latest.state, latest.failure_category, latest.retry_decision = "AMBIGUOUS", "CRASH_AFTER_SEND", "TERMINAL"
            slot.execution_owner = None
        session.flush()


def stable_sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _artifact() -> dict[str, Any]:
    if hashlib.sha256(RECONCILIATION_PATH.read_bytes()).hexdigest() != RECONCILIATION_SHA256:
        raise SourceCorrectedPreflightError("frozen reconciliation SHA mismatch")
    artifact = json.loads(RECONCILIATION_PATH.read_text(encoding="utf-8"))
    if artifact.get("artifact_identity") != "source-text-reconciliation-v1" or artifact.get("generation_policy") != "raw-human-row-source-text-v2":
        raise SourceCorrectedPreflightError("frozen reconciliation identity/policy mismatch")
    result = artifact.get("reconstructed_result", {})
    if (result.get("frozen_records"), result.get("source_exact"), result.get("source_correction_required"), result.get("unresolved")) != (1568, 1070, 498, 0):
        raise SourceCorrectedPreflightError("frozen reconciliation population mismatch")
    rows = artifact.get("records", [])
    affected = artifact.get("affected_record_keys", [])
    if len(rows) != 1568 or len(affected) != 498 or len(set(affected)) != 498 or set(affected) != {r["frozen_record_key"] for r in rows if r["status"] == "SOURCE_CORRECTION_REQUIRED"}:
        raise SourceCorrectedPreflightError("frozen affected-record set mismatch")
    return artifact


def _route(judge: str) -> str:
    spec = MODEL_REGISTRY[judge]
    return "OPENAI_DIRECT" if spec.provider is Provider.OPENAI else frozen_openrouter_route(judge)["upstream_provider"]


def _passes(condition: str, order: str) -> tuple[str, ...]:
    return ("AB", "BA") if order == "AB_BA" or condition == "DUAL_SWAP" else ("AB",)


def _rq(question: str) -> str:
    if question.startswith("How well do"): return "RQ1"
    if question.startswith("Does the same judge"): return "RQ2"
    if question.startswith("Does swapping"): return "RQ3"
    if question.startswith("Does redundant"): return "RQ4"
    if question.startswith("Does formatting"): return "RQ5"
    if question.startswith("Does a judge prefer"): return "RQ6"
    if question.startswith("When one answer"): return "RQ6"
    if question.startswith("Can dual-pass"): return "RQ7_PRIMARY"
    raise SourceCorrectedPreflightError("unknown historical controlled experiment")


def _source_texts(artifact: dict[str, Any]) -> dict[tuple[str, int, int, str], tuple[str, str]]:
    """Return raw text only after verifying the already-frozen map's hashes."""
    _, raw, _, _ = load_raw_source()
    found: dict[tuple[str, int, int, str], tuple[str, str]] = {}
    for row in artifact["records"]:
        key = (row["frozen_record_key"], int(row["question_id"]), int(row["turn"]), "source")
        try:
            a = raw[(int(row["question_id"]), int(row["turn"]), row["model_1"])].text
            b = raw[(int(row["question_id"]), int(row["turn"]), row["model_2"])].text
        except KeyError as exc:
            raise SourceCorrectedPreflightError("artifact source row absent from raw source") from exc
        if [sha(a), sha(b)] != row["corrected_source_answer_hashes"]:
            raise SourceCorrectedPreflightError("raw source text fails frozen corrected hash assertion")
        found[key] = (a, b)
    return found


@dataclass(frozen=True)
class Planned:
    planned_pass_id: str
    idempotency_key: str
    historical_identity: str
    rq_code: str
    condition_code: str
    judge_id: str
    provider: str
    route: str
    presentation: str
    prompt_id: int
    corrected_record_key: str
    payload_sha256: str
    input_tokens: int
    output_tokens: int
    expected_usd: Decimal
    reason: str
    details: dict[str, Any]

    def json(self) -> dict[str, Any]:
        return {**self.details, "planned_pass_id": self.planned_pass_id, "idempotency_key": self.idempotency_key,
                "historical_pass_identity": self.historical_identity, "rq_code": self.rq_code, "condition_code": self.condition_code,
                "judge_id": self.judge_id, "provider": self.provider, "route": self.route, "presentation": self.presentation,
                "prompt_id": self.prompt_id, "corrected_record_key": self.corrected_record_key, "rendered_payload_sha256": self.payload_sha256,
                "estimated_input_tokens": self.input_tokens, "estimated_output_tokens": self.output_tokens,
                "estimated_usd": str(self.expected_usd), "rerun_reason": self.reason}


def _estimate(messages: list[dict[str, str]], judge: str) -> tuple[int, int, Decimal]:
    # Frozen, provider-neutral character estimate.  The real executor records
    # usage; this is an explicit hard-cap reservation forecast, not a claim of
    # tokenizer-exact billing units.
    inp = math.ceil(sum(len(m["content"]) for m in messages) / 4)
    out = MODEL_REGISTRY[judge].max_output_tokens
    rate = price_for_model(judge)
    return inp, out, Decimal(inp) * rate.input_per_token + Decimal(out) * rate.output_per_token


def _unit_rows(session: Session, records: dict[str, dict[str, Any]], sources: dict[tuple[str, int, int, str], tuple[str, str]]) -> tuple[list[Planned], list[dict[str, Any]]]:
    a, b = aliased(Answer), aliased(Answer)
    stmt = select(ExperimentalUnit.id, ExperimentalUnit.condition_code, ExperimentalUnit.presentation_order, ExperimentalUnit.judge_model,
                  ExperimentalUnit.provider, ExperimentalUnit.provider_model, ExperimentalUnit.repetition_index, ExperimentalUnit.temperature,
                  ExperimentalUnit.top_p, ExperimentalUnit.seed, ExperimentalUnit.prompt_template_version, ExperimentalUnit.unit_fingerprint,
                  ExperimentalUnit.prompt_id, ExperimentalUnit.answer_a_id, ExperimentalUnit.answer_b_id, ExperimentalUnit.answer_a_author_id,
                  ExperimentalUnit.answer_b_author_id, ExperimentalUnit.human_label, Prompt.text, a.text, a.model_name, b.text, b.model_name,
                  Experiment.research_question).join(Prompt, Prompt.id == ExperimentalUnit.prompt_id).join(a, a.id == ExperimentalUnit.answer_a_id).join(b, b.id == ExperimentalUnit.answer_b_id).join(Experiment, Experiment.id == ExperimentalUnit.experiment_id)
    planned: list[Planned] = []; reuse: list[dict[str, Any]] = []
    for row in session.execute(stmt):
        (unit_id, condition, order, judge, provider, provider_model, repetition, temperature, top_p, seed, template, unit_fp,
         prompt_id, a_id, b_id, aa, ba, label, question, old_a, old_am, old_b, old_bm, question_rq) = row
        key = FrozenRecord(prompt_id, a_id, b_id, model_name(aa or old_am), model_name(ba or old_bm), old_a, old_b, label or "", question).key
        record = records.get(key)
        if record is None: raise SourceCorrectedPreflightError("controlled unit has no frozen reconciliation record")
        corrected_a, corrected_b = sources[(key, int(record["question_id"]), int(record["turn"]), "source")]
        rq = _rq(question_rq)
        # RQ4/5 show original-vs-deterministically-transformed answer A; B is
        # deliberately not a displayed payload.  The correction comparison is
        # therefore payload-level, not pair-level.
        transform = None
        changed = record["status"] == "SOURCE_CORRECTION_REQUIRED"
        if rq == "RQ4": transform = "VERBOSITY_REDUNDANCY"; changed = sha(old_a) != sha(corrected_a)
        if rq == "RQ5": transform = "FORMAT_ONLY"; changed = sha(old_a) != sha(corrected_a)
        for number, presentation in enumerate(_passes(condition, order), 1):
            identity = f"controlled:{unit_id}:{number}"
            old_payload = {"prompt": sha(question), "a": sha(old_a), "b": sha(old_b), "presentation": presentation, "transform": transform}
            if not changed:
                reuse.append({"historical_pass_identity": identity, "classification": "SOURCE_CORRECT_REUSABLE", "identity_sha256": stable_sha(old_payload), "planned_pass_id": None,
                              "details": {"rq_code": rq, "unit_id": str(unit_id), "exact_identity_checks": old_payload}})
                continue
            display_a, display_b = corrected_a, corrected_b
            if transform == "VERBOSITY_REDUNDANCY": display_b = make_verbosity_variant(corrected_a)
            elif transform == "FORMAT_ONLY": display_b = make_format_variant(corrected_a)
            if presentation == "BA": display_a, display_b = display_b, display_a
            messages = build_messages(question=question, answer_a=display_a, answer_b=display_b)
            payload = {"messages": messages, "prompt_template_version": PROMPT_TEMPLATE_VERSION, "prompt_hash": prompt_hash(), "judge": judge,
                       "provider": provider, "provider_model": provider_model, "route": _route(judge), "temperature": str(temperature), "top_p": str(top_p), "seed": seed,
                       "presentation": presentation, "transform": transform}
            payload_sha = stable_sha(payload); inp, out, usd = _estimate(messages, judge)
            pass_id = stable_sha({"manifest": MANIFEST_IDENTITY, "historical": identity, "payload": payload_sha})
            idem = stable_sha({"source-corrected-idempotency-v1": pass_id})
            detail = {"corrected_dataset_version": DATASET_VERSION, "reconciliation_sha256": RECONCILIATION_SHA256, "source_question_id": record["question_id"], "source_turn": record["turn"],
                      "corrected_source_answer_hashes": record["corrected_source_answer_hashes"], "historical_source_answer_hashes": record["frozen_answer_hashes"], "prompt_sha256": sha(question),
                      "prompt_template_version": PROMPT_TEMPLATE_VERSION, "prompt_template_sha256": prompt_hash(), "routing_policy_version": routing_policy_version(), "routing_fingerprint": routing_fingerprint(),
                      "provider_model": provider_model, "temperature": str(temperature), "top_p": str(top_p), "seed": seed, "repetition_index": repetition,
                      "transform": transform, "retry_policy_version": RETRY_POLICY_VERSION, "failure_policy_version": FAILURE_POLICY_VERSION, "fallbacks_allowed": False,
                      "unit_fingerprint": unit_fp, "source_corrected_payload": {"answer_a_sha256": sha(display_a), "answer_b_sha256": sha(display_b)}}
            planned.append(Planned(pass_id, idem, identity, rq, condition, judge, provider, _route(judge), presentation, prompt_id, key, payload_sha, inp, out, usd, "CORRECTED_RERUN_REQUIRED", detail))
            reuse.append({"historical_pass_identity": identity, "classification": "CORRECTED_RERUN_REQUIRED", "identity_sha256": stable_sha(old_payload), "planned_pass_id": pass_id,
                          "details": {"rq_code": rq, "unit_id": str(unit_id), "exact_identity_checks": old_payload}})
    return planned, reuse


def _multijudge_rows(session: Session, artifact: dict[str, Any], sources: dict[tuple[str, int, int, str], tuple[str, str]]) -> tuple[list[Planned], list[dict[str, Any]]]:
    historical = json.loads((ROOT / "evidence" / "multijudge_consensus" / "execution_manifest_v1.json").read_text(encoding="utf-8"))
    pair_records = {tuple(sorted(row["frozen_answer_ids"])): row for row in artifact["records"]}
    pairs = {row["canonical_pair_id"]: row for row in historical["pairs"]}; planned: list[Planned] = []; reuse: list[dict[str, Any]] = []
    prompts = {int(pid): text for pid, text in session.execute(select(Prompt.id, Prompt.text))}
    affected_pairs: set[str] = set()
    for pair_id, pair in pairs.items():
        record = pair_records.get(tuple(sorted((pair["original_answer_1_id"], pair["original_answer_2_id"]))))
        if record is not None and record["status"] == "SOURCE_CORRECTION_REQUIRED": affected_pairs.add(pair_id)
    if len(affected_pairs) != 498: raise SourceCorrectedPreflightError("affected multi-judge pair membership does not align to 498 frozen records")
    _, raw, _, _ = load_raw_source()
    for row in historical["planned_passes"]:
        identity = f"multijudge:{row['planned_pass_id']}"; pair = pairs[row["canonical_pair_id"]]
        record = pair_records.get(tuple(sorted((pair["original_answer_1_id"], pair["original_answer_2_id"]))))
        if record is None:
            # These historical pairs are outside the frozen 1,568-record
            # correction population.  C2 must neither infer source identity
            # nor relabel them as reusable.
            reuse.append({"historical_pass_identity": identity, "classification": "HISTORICAL_ONLY_UNALIGNED", "identity_sha256": stable_sha(row), "planned_pass_id": None, "details": {"rq_code": "RQ7_SECONDARY", "canonical_pair_id": row["canonical_pair_id"], "reason": "OUTSIDE_FROZEN_CORRECTED_POPULATION"}})
            continue
        if row["canonical_pair_id"] not in affected_pairs:
            reuse.append({"historical_pass_identity": identity, "classification": "SOURCE_CORRECT_REUSABLE", "identity_sha256": stable_sha(row), "planned_pass_id": None, "details": {"rq_code": "RQ7_SECONDARY", "canonical_pair_id": row["canonical_pair_id"]}}); continue
        a = raw[(record["question_id"], record["turn"], record["model_1"])].text; b = raw[(record["question_id"], record["turn"], record["model_2"])].text
        if [sha(a), sha(b)] != record["corrected_source_answer_hashes"]: raise SourceCorrectedPreflightError("multi-judge raw source hash mismatch")
        if row["presentation"] == "BA": a, b = b, a
        question = prompts.get(int(pair["prompt_id"]))
        if not question: raise SourceCorrectedPreflightError("historical multi-judge manifest lacks exact prompt payload")
        judge = row["judge_id"]; messages = build_messages(question=question, answer_a=a, answer_b=b)
        payload = {"messages": messages, "judge": judge, "route": _route(judge), "presentation": row["presentation"], "prompt_hash": prompt_hash()}
        payload_sha = stable_sha(payload); inp, out, usd = _estimate(messages, judge); pass_id = stable_sha({"manifest": MANIFEST_IDENTITY, "historical": identity, "payload": payload_sha})
        detail = {"corrected_dataset_version": DATASET_VERSION, "reconciliation_sha256": RECONCILIATION_SHA256, "source_question_id": record["question_id"], "source_turn": record["turn"], "corrected_source_answer_hashes": record["corrected_source_answer_hashes"], "prompt_sha256": sha(question), "prompt_template_version": PROMPT_TEMPLATE_VERSION, "prompt_template_sha256": prompt_hash(), "routing_policy_version": routing_policy_version(), "routing_fingerprint": routing_fingerprint(), "transform": None, "retry_policy_version": RETRY_POLICY_VERSION, "failure_policy_version": FAILURE_POLICY_VERSION, "fallbacks_allowed": False, "canonical_pair_id": row["canonical_pair_id"], "source_corrected_payload": {"answer_a_sha256": sha(a), "answer_b_sha256": sha(b)}}
        planned.append(Planned(pass_id, stable_sha({"source-corrected-idempotency-v1": pass_id}), identity, "RQ7_SECONDARY", "MULTIJUDGE_CONSENSUS", judge, MODEL_REGISTRY[judge].provider.value, _route(judge), row["presentation"], int(pair["prompt_id"]), record["frozen_record_key"], payload_sha, inp, out, usd, "CORRECTED_RERUN_REQUIRED", detail))
        reuse.append({"historical_pass_identity": identity, "classification": "CORRECTED_RERUN_REQUIRED", "identity_sha256": stable_sha(row), "planned_pass_id": pass_id, "details": {"rq_code": "RQ7_SECONDARY", "canonical_pair_id": row["canonical_pair_id"]}})
    return planned, reuse


def build_plan(session: Session) -> tuple[dict[str, Any], dict[str, Any]]:
    artifact = _artifact(); records = {r["frozen_record_key"]: r for r in artifact["records"]}; sources = _source_texts(artifact)
    standard, reuse_a = _unit_rows(session, records, sources); secondary, reuse_b = _multijudge_rows(session, artifact, sources)
    slots = sorted(standard + secondary, key=lambda row: row.planned_pass_id); reuse = sorted(reuse_a + reuse_b, key=lambda row: row["historical_pass_identity"])
    if len({p.planned_pass_id for p in slots}) != len(slots) or len({p.idempotency_key for p in slots}) != len(slots): raise SourceCorrectedPreflightError("execution idempotency collision")
    if len(reuse) != 24004 or len({r["historical_pass_identity"] for r in reuse}) != len(reuse): raise SourceCorrectedPreflightError("historical pass-reuse ledger is incomplete")
    if sum(r["classification"] == "CORRECTED_RERUN_REQUIRED" for r in reuse) != len(slots): raise SourceCorrectedPreflightError("rerun/reuse ledger disagreement")
    per_rq, per_judge = Counter(p.rq_code for p in slots), Counter(p.judge_id for p in slots)
    totals = {"input_tokens": sum(p.input_tokens for p in slots), "output_tokens": sum(p.output_tokens for p in slots), "expected_usd": sum((p.expected_usd for p in slots), Decimal("0"))}
    provider_cost = {provider: sum((p.expected_usd for p in slots if p.provider == provider), Decimal("0")) for provider in {p.provider for p in slots}}
    # P90 reservation uses the 90th percentile corrected payload forecast for
    # every call per provider; the extra 15% is the final fail-closed envelope.
    p90_cost = Decimal("0")
    for judge in JUDGES:
        costs = sorted(p.expected_usd for p in slots if p.judge_id == judge)
        if costs: p90_cost += costs[math.ceil(.90 * len(costs)) - 1] * len(costs)
    p90_15 = (p90_cost * Decimal("1.15")).quantize(Decimal("0.00000001"), rounding=ROUND_UP)
    provider_caps = {provider: str((sum((p.expected_usd for p in slots if p.provider == provider), Decimal("0")) * Decimal("1.15")).quantize(Decimal("0.00000001"), rounding=ROUND_UP)) for provider in provider_cost}
    manifest = {"manifest_identity": MANIFEST_IDENTITY, "execution_authorized": False, "dataset_version": DATASET_VERSION, "reconciliation_artifact": {"identity": artifact["artifact_identity"], "sha256": RECONCILIATION_SHA256, "affected_record_keys_consumed": 498, "heuristic_rediscovery": False}, "scientific_configuration": {"prompt_template_version": PROMPT_TEMPLATE_VERSION, "prompt_template_sha256": prompt_hash(), "routing_policy_version": routing_policy_version(), "routing_fingerprint": routing_fingerprint(), "retry_policy_version": RETRY_POLICY_VERSION, "failure_policy_version": FAILURE_POLICY_VERSION, "fallbacks_allowed": False, "judges": [{"judge_id": j, "provider": MODEL_REGISTRY[j].provider.value, "requested_model": MODEL_REGISTRY[j].requested_model, "route": _route(j)} for j in JUDGES]}, "planned_passes": [p.json() for p in slots], "counts": {"total_rerun_passes": len(slots), "per_rq": dict(sorted(per_rq.items())), "per_judge": dict(sorted(per_judge.items())), "reusable_historical_passes": sum(r["classification"] == "SOURCE_CORRECT_REUSABLE" for r in reuse), "historical_only_unaligned_passes": sum(r["classification"] == "HISTORICAL_ONLY_UNALIGNED" for r in reuse), "historical_total_passes": len(reuse)}, "budget_metadata": {"pricing_version": PRICING_CONFIG["version"], "actual_corrected_input_tokens": totals["input_tokens"], "estimated_output_tokens": totals["output_tokens"], "expected_usd": str(totals["expected_usd"]), "provider_expected_usd": {k: str(v) for k, v in provider_cost.items()}, "p90_usd": str(p90_cost), "p90_plus_15_percent_usd": str(p90_15), "global_hard_cap_usd": str(p90_15), "provider_hard_caps_usd": provider_caps, "budget_guard": "FAIL_CLOSED_PRE_TRANSPORT"}, "future_analysis_runs": [{"identity": f"controlled-source-text-corrected-{rq.lower()}-analysis-v1", "rq_code": rq, "status": "PROPOSED_NOT_CALCULATED"} for rq in ("RQ1", "RQ2", "RQ3", "RQ4", "RQ5", "RQ6", "RQ7_PRIMARY", "RQ7_SECONDARY")], "future_evidence_package": "evidence/final/controlled_source_text_corrected_v1/", "future_release": "research_release_v4", "provider_calls": 0}
    manifest["manifest_sha256"] = stable_sha({k: v for k, v in manifest.items() if k != "manifest_sha256"})
    ledger = {"ledger_identity": "controlled-source-text-corrected-reuse-ledger-v1", "manifest_sha256": manifest["manifest_sha256"], "historical_passes": reuse}
    ledger["ledger_sha256"] = stable_sha({k: v for k, v in ledger.items() if k != "ledger_sha256"})
    return manifest, ledger


def write_plan(manifest: dict[str, Any], ledger: dict[str, Any]) -> None:
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REUSE_LEDGER_PATH.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def mock_dry_run(manifest: dict[str, Any]) -> dict[str, Any]:
    rows = manifest["planned_passes"]
    if manifest.get("execution_authorized") is not False or len(rows) != manifest["counts"]["total_rerun_passes"]: raise SourceCorrectedPreflightError("mock dry run authorization/count mismatch")
    if len({r["idempotency_key"] for r in rows}) != len(rows) or any(r["fallbacks_allowed"] for r in rows): raise SourceCorrectedPreflightError("mock dry run idempotency/routing mismatch")
    if any(r["reconciliation_sha256"] != RECONCILIATION_SHA256 or r["corrected_dataset_version"] != DATASET_VERSION for r in rows): raise SourceCorrectedPreflightError("mock dry run source-correction provenance mismatch")
    return {"status": "PASS", "mock_transport_calls": len(rows), "provider_calls": 0, "network": "DISABLED", "execution_authorized": False}


def materialize(session: Session, manifest: dict[str, Any], ledger: dict[str, Any]) -> SourceCorrectedExecutionBatch:
    version = session.scalar(select(DatasetVersion).where(DatasetVersion.version == DATASET_VERSION, DatasetVersion.source_checksum == RECONCILIATION_SHA256))
    if version is None:
        version = DatasetVersion(source_name="judgelab-canonical-human-reference", version=DATASET_VERSION, source_checksum=RECONCILIATION_SHA256, checksum_algorithm="SHA-256", import_status="SUCCEEDED", imported_prompt_count=1568, notes="Additive source-text corrected DatasetVersion; correction authority is source-text-reconciliation-v1.")
        session.add(version); session.flush()
    batch = session.scalar(select(SourceCorrectedExecutionBatch).where(SourceCorrectedExecutionBatch.manifest_sha256 == manifest["manifest_sha256"]))
    # A C2 preflight can be rerun after a planner-only metadata correction.  A
    # never-executed materialized batch is safely reconciled in place rather
    # than leaving a second, stale future ledger beside the canonical plan.
    if batch is None:
        batch = session.scalar(select(SourceCorrectedExecutionBatch).where(
            SourceCorrectedExecutionBatch.dataset_version_id == version.id,
            SourceCorrectedExecutionBatch.reconciliation_sha256 == RECONCILIATION_SHA256,
            SourceCorrectedExecutionBatch.manifest_identity == MANIFEST_IDENTITY,
        ))
        if batch is not None:
            attempted = session.scalar(select(SourceCorrectedExecutionSlot.id).where(SourceCorrectedExecutionSlot.batch_id == batch.id, SourceCorrectedExecutionSlot.attempt_count > 0))
            if attempted is not None or batch.status != "MATERIALIZED":
                raise SourceCorrectedPreflightError("cannot reconcile an execution-started corrected batch")
            batch.manifest_sha256 = manifest["manifest_sha256"]
            batch.global_hard_cap_usd = Decimal(manifest["budget_metadata"]["global_hard_cap_usd"])
            batch.provider_hard_caps_json = manifest["budget_metadata"]["provider_hard_caps_usd"]
    if batch is None:
        batch = SourceCorrectedExecutionBatch(dataset_version_id=version.id, reconciliation_sha256=RECONCILIATION_SHA256, manifest_identity=MANIFEST_IDENTITY, manifest_sha256=manifest["manifest_sha256"], global_hard_cap_usd=Decimal(manifest["budget_metadata"]["global_hard_cap_usd"]), provider_hard_caps_json=manifest["budget_metadata"]["provider_hard_caps_usd"], status="MATERIALIZED", provenance_json={"provider_calls": 0, "execution_authorized": False, "retry_resume_crash_states": ["PENDING", "RESERVED", "SENT", "COMPLETED", "FAILED", "AMBIGUOUS"]})
        session.add(batch); session.flush()
    existing_slots = {slot.planned_pass_id: slot for slot in session.scalars(select(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == batch.id))}
    canonical_ids = {row["planned_pass_id"] for row in manifest["planned_passes"]}
    # This branch is reachable only while C2 is still materializing an
    # unexecuted plan.  It removes a superseded *future* slot identity caused
    # by a deterministic planner correction; a started slot is never altered.
    obsolete = [slot for pass_id, slot in existing_slots.items() if pass_id not in canonical_ids]
    if obsolete:
        if any(slot.attempt_count or slot.state != "PENDING" for slot in obsolete):
            raise SourceCorrectedPreflightError("cannot replace an execution-started corrected slot")
        for slot in obsolete: session.delete(slot)
        session.flush(); existing_slots = {slot.planned_pass_id: slot for slot in session.scalars(select(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == batch.id))}
    for row in manifest["planned_passes"]:
        slot = existing_slots.get(row["planned_pass_id"])
        if slot is not None:
            if slot.idempotency_key != row["idempotency_key"] or slot.payload_sha256 != row["rendered_payload_sha256"]:
                raise SourceCorrectedPreflightError("existing corrected slot payload identity drift")
            model = row.get("provider_model", MODEL_REGISTRY[row["judge_id"]].requested_model)
            slot.rq_code, slot.condition_code, slot.requested_model, slot.presentation, slot.corrected_record_key = row["rq_code"], row["condition_code"], model, row["presentation"], row["corrected_record_key"]
    additions = [SourceCorrectedExecutionSlot(batch_id=batch.id, planned_pass_id=r["planned_pass_id"], idempotency_key=r["idempotency_key"], rq_code=r["rq_code"], condition_code=r["condition_code"], judge_id=r["judge_id"], provider=r["provider"], requested_model=r.get("provider_model", MODEL_REGISTRY[r["judge_id"]].requested_model), route=r["route"], presentation=r["presentation"], corrected_record_key=r["corrected_record_key"], payload_sha256=r["rendered_payload_sha256"], state="PENDING", estimated_input_tokens=r["estimated_input_tokens"], estimated_output_tokens=r["estimated_output_tokens"]) for r in manifest["planned_passes"] if r["planned_pass_id"] not in existing_slots]
    if additions: session.add_all(additions); session.flush()
    existing_reuse = {row.historical_pass_identity: row for row in session.scalars(select(SourceCorrectedReuseLedger).where(SourceCorrectedReuseLedger.batch_id == batch.id))}
    for row in ledger["historical_passes"]:
        historical = existing_reuse.get(row["historical_pass_identity"])
        if historical is not None:
            if historical.identity_sha256 != row["identity_sha256"]:
                raise SourceCorrectedPreflightError("existing reuse ledger identity drift")
            historical.classification, historical.planned_pass_id, historical.details_json = row["classification"], row["planned_pass_id"], row["details"]
    rows = [SourceCorrectedReuseLedger(batch_id=batch.id, historical_pass_identity=r["historical_pass_identity"], classification=r["classification"], identity_sha256=r["identity_sha256"], planned_pass_id=r["planned_pass_id"], details_json=r["details"]) for r in ledger["historical_passes"] if r["historical_pass_identity"] not in existing_reuse]
    if rows: session.add_all(rows); session.flush()
    if len(session.scalars(select(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == batch.id)).all()) != len(manifest["planned_passes"]): raise SourceCorrectedPreflightError("durable corrected slot materialization mismatch")
    if len(session.scalars(select(SourceCorrectedReuseLedger).where(SourceCorrectedReuseLedger.batch_id == batch.id)).all()) != len(ledger["historical_passes"]): raise SourceCorrectedPreflightError("durable reuse ledger materialization mismatch")
    return batch


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--preflight", action="store_true"); parser.add_argument("--status", action="store_true"); parser.add_argument("--reconcile-stale-in-flight", action="store_true"); parser.add_argument("--execute", action="store_true"); parser.add_argument("--confirm-paid-execution")
    args = parser.parse_args()
    if args.execute and args.confirm_paid_execution != CONFIRMATION: raise SourceCorrectedPreflightError("paid execution requires the exact confirmation phrase")
    from backend.core.database import SessionLocal
    from backend.historical.source_corrected_execution import SourceCorrectedRunner, render_dashboard
    if args.status:
        report, caps = SourceCorrectedRunner(SessionLocal).status()
        print(render_dashboard(report, caps)); return 0
    if args.reconcile_stale_in_flight:
        runner = SourceCorrectedRunner(SessionLocal)
        report = runner.reconcile_stale_in_flight()
        _, caps = runner.status()
        print(render_dashboard(report, caps)); return 0
    if args.execute:
        def progress(report, caps, elapsed, rate):
            dashboard = render_dashboard(report, caps, elapsed=elapsed, rate=rate)
            if sys.stdout.isatty(): print("\x1b[H\x1b[2J" + dashboard, flush=True)
            else: print(dashboard, flush=True)
        report = SourceCorrectedRunner(SessionLocal).execute(confirmation=args.confirm_paid_execution, progress=progress)
        print("SOURCE-CORRECTED EXECUTION COMPLETE" if report["completed"] == report["planned"] else "SOURCE-CORRECTED EXECUTION STOPPED")
        return 0
    with SessionLocal() as session:
        manifest, ledger = build_plan(session); write_plan(manifest, ledger); dry = mock_dry_run(manifest); batch = materialize(session, manifest, ledger); batch_id = str(batch.id); session.commit()
    PREFLIGHT_PATH.write_text(json.dumps({"preflight_identity": "controlled-source-text-corrected-preflight-v1", "manifest_sha256": manifest["manifest_sha256"], "dry_run": dry, "batch_id": batch_id, "execution_authorized": False, "provider_calls": 0}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"manifest_sha256": manifest["manifest_sha256"], "rerun_passes": manifest["counts"]["total_rerun_passes"], "dry_run": dry}, sort_keys=True)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
