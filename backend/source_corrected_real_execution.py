"""Durable executor for the frozen source-text-corrected manifest.

The executor resolves request text only by the already-frozen record key,
question/turn/model fields and hashes in the manifest.  It never re-runs the
reconciliation heuristic and it never reads historical decisions as input.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from time import monotonic, sleep
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from build_source_text_reconciliation import load_raw_source, sha
from controlled_evaluation import ControlledEvaluationEngine, EvaluationRequest, NormalizedEvaluationResult
from controlled_persistence import Outcome
from controlled_prompt import PROMPT_TEMPLATE_VERSION, build_messages, prompt_hash
from controlled_providers import ProviderExecutionGate, Transport, adapter_for_judge, environment_http_transport
from controlled_transforms import make_format_variant, make_verbosity_variant
from execution_policy import next_backoff_seconds, retry_rule
from model_registry import MODEL_REGISTRY, Provider
from models import Prompt
from pricing import CONFIG as PRICING_CONFIG, price_for_model
from source_corrected_execution import (DATASET_VERSION, MANIFEST_IDENTITY, MANIFEST_PATH, RECONCILIATION_PATH,
                                        RECONCILIATION_SHA256, SourceCorrectedPreflightError, stable_sha)
from source_corrected_execution_models import (SourceCorrectedExecutionAttempt, SourceCorrectedExecutionBatch,
                                               SourceCorrectedExecutionSlot)


LEASE_SECONDS = 300
TOTAL = 6449
TERMINAL = {"COMPLETED", "FAILED", "AMBIGUOUS"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """Normalize legacy/SQLite naïve timestamps before lease comparison."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def credentials_present() -> dict[str, bool]:
    return {"OPENAI": bool(os.getenv("OPENAI_API_KEY", "").strip()), "OPENROUTER": bool(os.getenv("OPENROUTER_API_KEY", "").strip())}


def load_manifest() -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("manifest_identity") != MANIFEST_IDENTITY or manifest.get("manifest_sha256") != "331d4498d5fe1b86d544366a3579e8f35344e518894350c0b8d339c55f16d742":
        raise SourceCorrectedPreflightError("source-corrected manifest identity/SHA mismatch")
    if manifest.get("execution_authorized") is not False or len(manifest.get("planned_passes", [])) != TOTAL:
        raise SourceCorrectedPreflightError("source-corrected manifest execution/count mismatch")
    if len({row["idempotency_key"] for row in manifest["planned_passes"]}) != TOTAL or any(row.get("fallbacks_allowed") for row in manifest["planned_passes"]):
        raise SourceCorrectedPreflightError("source-corrected manifest idempotency/routing mismatch")
    return manifest


class FrozenPayloadResolver:
    def __init__(self, manifest: dict[str, Any]) -> None:
        artifact = json.loads(RECONCILIATION_PATH.read_text(encoding="utf-8"))
        if sha(RECONCILIATION_PATH.read_bytes()) != RECONCILIATION_SHA256:
            raise SourceCorrectedPreflightError("reconciliation artifact SHA mismatch")
        self.records = {row["frozen_record_key"]: row for row in artifact["records"]}
        self.rows = {row["planned_pass_id"]: row for row in manifest["planned_passes"]}
        _, self.raw, _, _ = load_raw_source()

    def payload(self, session: Session, slot: SourceCorrectedExecutionSlot) -> tuple[dict[str, Any], EvaluationRequest]:
        row = self.rows.get(slot.planned_pass_id)
        if row is None or row["rendered_payload_sha256"] != slot.payload_sha256 or row["idempotency_key"] != slot.idempotency_key:
            raise SourceCorrectedPreflightError("durable slot does not match frozen manifest")
        if row["corrected_dataset_version"] != DATASET_VERSION or row["reconciliation_sha256"] != RECONCILIATION_SHA256:
            raise SourceCorrectedPreflightError("corrected dataset/reconciliation identity mismatch")
        record = self.records.get(row["corrected_record_key"])
        if record is None or record["status"] != "SOURCE_CORRECTION_REQUIRED":
            raise SourceCorrectedPreflightError("manifest slot lacks an explicit frozen correction mapping")
        if (record["question_id"], record["turn"], record["corrected_source_answer_hashes"]) != (row["source_question_id"], row["source_turn"], row["corrected_source_answer_hashes"]):
            raise SourceCorrectedPreflightError("frozen source question/turn/hash identity mismatch")
        try:
            first = self.raw[(record["question_id"], record["turn"], record["model_1"])].text
            second = self.raw[(record["question_id"], record["turn"], record["model_2"])].text
        except KeyError as exc:
            raise SourceCorrectedPreflightError("frozen raw assistant answer is unavailable") from exc
        if [sha(first), sha(second)] != record["corrected_source_answer_hashes"]:
            raise SourceCorrectedPreflightError("raw assistant payload hash mismatch")
        prompt = session.get(Prompt, row["prompt_id"])
        if prompt is None or sha(prompt.text) != row["prompt_sha256"]:
            raise SourceCorrectedPreflightError("frozen prompt identity mismatch")
        transform = row.get("transform")
        a, b = first, second
        if transform == "VERBOSITY_REDUNDANCY": b = make_verbosity_variant(first)
        elif transform == "FORMAT_ONLY": b = make_format_variant(first)
        elif transform is not None: raise SourceCorrectedPreflightError("unknown frozen transform")
        if row["presentation"] == "BA": a, b = b, a
        if not a.strip() or not b.strip() or sha(a) == sha(prompt.text) or sha(b) == sha(prompt.text):
            raise SourceCorrectedPreflightError("prompt-as-answer contamination")
        if "vicuna-13b-v1.3" in json.dumps(record).lower():
            raise SourceCorrectedPreflightError("Vicuna v1.3 contamination")
        messages = build_messages(question=prompt.text, answer_a=a, answer_b=b)
        if row["condition_code"] == "MULTIJUDGE_CONSENSUS":
            identity = {"messages": messages, "judge": row["judge_id"], "route": row["route"], "presentation": row["presentation"], "prompt_hash": prompt_hash()}
        else:
            identity = {"messages": messages, "prompt_template_version": PROMPT_TEMPLATE_VERSION, "prompt_hash": prompt_hash(), "judge": row["judge_id"], "provider": row["provider"], "provider_model": row["provider_model"], "route": row["route"], "temperature": row["temperature"], "top_p": row["top_p"], "seed": row["seed"], "presentation": row["presentation"], "transform": transform}
        if stable_sha(identity) != row["rendered_payload_sha256"]:
            raise SourceCorrectedPreflightError("rendered payload hash mismatch")
        ids = record["frozen_answer_ids"]
        presented = (ids[1], ids[0]) if row["presentation"] == "BA" else tuple(ids)
        requested_model = row.get("provider_model", MODEL_REGISTRY[row["judge_id"]].requested_model)
        request = EvaluationRequest(question=prompt.text, answer_a=a, answer_b=b, judge_name=row["judge_id"], provider=Provider(row["provider"]), requested_model=requested_model, temperature=float(row.get("temperature") or 0), top_p=float(row.get("top_p") or 1), seed=row.get("seed"), prompt_template_version=PROMPT_TEMPLATE_VERSION, experiment_id=slot.id, controlled_unit_id=slot.id, repetition_index=int(row.get("repetition_index") or 0), pass_number=1, original_answer_a_id=ids[0], original_answer_b_id=ids[1], presented_answer_a_id=presented[0], presented_answer_b_id=presented[1], presentation_provenance={"source_corrected_manifest": MANIFEST_IDENTITY, "payload_sha256": slot.payload_sha256, "transform": transform})
        return row, request


class SourceCorrectedStore:
    def _costs(self, session: Session, batch_id: Any, provider: str | None = None) -> Decimal:
        stmt = select(func.coalesce(func.sum(func.coalesce(SourceCorrectedExecutionAttempt.actual_usd, SourceCorrectedExecutionAttempt.reserved_usd)), Decimal("0"))).join(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == batch_id)
        if provider: stmt = stmt.where(SourceCorrectedExecutionSlot.provider == provider)
        return Decimal(session.scalar(stmt) or 0)

    def recover(self, session: Session, batch: SourceCorrectedExecutionBatch) -> None:
        now = utc_now()
        for slot in session.scalars(select(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == batch.id, SourceCorrectedExecutionSlot.state.in_(("RESERVED", "SENT"))).with_for_update()):
            if slot.lease_expires_at and as_utc(slot.lease_expires_at) > now: continue
            attempt = session.scalar(select(SourceCorrectedExecutionAttempt).where(SourceCorrectedExecutionAttempt.slot_id == slot.id).order_by(SourceCorrectedExecutionAttempt.attempt_index.desc()))
            if slot.state == "RESERVED":
                slot.state, slot.execution_owner, slot.lease_expires_at, slot.reserved_usd = "PENDING", None, None, Decimal("0")
                if attempt:
                    # A reservation that never crossed the transport boundary
                    # cannot consume budget and is safe to re-claim.
                    attempt.state, attempt.retry_decision, attempt.reserved_usd, attempt.completed_at = "ABORTED_BEFORE_TRANSPORT", "RETRY", Decimal("0"), now
            else:
                slot.state, slot.final_outcome, slot.error_category, slot.execution_owner, slot.lease_expires_at, slot.completed_at = "AMBIGUOUS", "AMBIGUOUS", "CRASH_AFTER_SEND", None, None, now
                if attempt: attempt.state, attempt.failure_category, attempt.retry_decision, attempt.completed_at = "AMBIGUOUS", "CRASH_AFTER_SEND", "TERMINAL", now

    def claim(self, session: Session, batch: SourceCorrectedExecutionBatch, *, owner: str) -> tuple[SourceCorrectedExecutionSlot, SourceCorrectedExecutionAttempt] | None:
        now = utc_now()
        slot = session.scalar(select(SourceCorrectedExecutionSlot).where(
            SourceCorrectedExecutionSlot.batch_id == batch.id,
            SourceCorrectedExecutionSlot.state == "PENDING",
            or_(SourceCorrectedExecutionSlot.next_eligible_at.is_(None), SourceCorrectedExecutionSlot.next_eligible_at <= now),
        ).order_by(SourceCorrectedExecutionSlot.planned_pass_id).with_for_update(skip_locked=True))
        if slot is None: return None
        forecast = Decimal(slot.estimated_input_tokens) * price_for_model(slot.judge_id).input_per_token + Decimal(slot.estimated_output_tokens) * price_for_model(slot.judge_id).output_per_token
        caps = {key: Decimal(value) for key, value in batch.provider_hard_caps_json.items()}
        if self._costs(session, batch.id) + forecast > Decimal(batch.global_hard_cap_usd) or self._costs(session, batch.id, slot.provider) + forecast > caps[slot.provider]:
            now=utc_now(); attempt=SourceCorrectedExecutionAttempt(slot_id=slot.id,attempt_id=stable_sha({"slot":slot.planned_pass_id,"attempt":slot.attempt_count,"budget":True}),attempt_index=slot.attempt_count,state="BLOCKED_BUDGET",failure_category="BUDGET_EXCEEDED",retry_decision="TERMINAL",reserved_usd=Decimal("0"),completed_at=now,details_json={"blocked_before_transport":True,"provider":slot.provider})
            slot.state, slot.attempt_count, slot.final_outcome, slot.error_category, slot.completed_at = "FAILED", slot.attempt_count+1, "MISSING_PASS", "BUDGET_EXCEEDED", now; session.add(attempt); session.flush(); return None
        attempt = SourceCorrectedExecutionAttempt(slot_id=slot.id, attempt_id=stable_sha({"slot": slot.planned_pass_id, "attempt": slot.attempt_count}), attempt_index=slot.attempt_count, state="RESERVED", reserved_usd=forecast, details_json={"owner": owner, "payload_sha256": slot.payload_sha256})
        slot.state, slot.attempt_count, slot.execution_owner, slot.lease_expires_at, slot.next_eligible_at, slot.reserved_usd, slot.started_at = "RESERVED", slot.attempt_count + 1, owner, now + timedelta(seconds=LEASE_SECONDS), None, forecast, slot.started_at or now; batch.status = "RUNNING"; session.add(attempt); session.flush(); return slot, attempt

    def mark_sent(self, session: Session, slot_id: Any, attempt_id: str, *, owner: str) -> SourceCorrectedExecutionSlot:
        slot = session.scalar(select(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.id == slot_id).with_for_update()); attempt = session.scalar(select(SourceCorrectedExecutionAttempt).where(SourceCorrectedExecutionAttempt.attempt_id == attempt_id).with_for_update())
        if slot is None or attempt is None or slot.state != "RESERVED" or slot.execution_owner != owner or attempt.state != "RESERVED": raise SourceCorrectedPreflightError("duplicate or invalid send claim")
        slot.state, attempt.state = "SENT", "SENT"; session.flush(); return slot

    def fail_before_send(self, session: Session, slot_id: Any, attempt_id: str, *, owner: str, reason: str) -> None:
        slot=session.scalar(select(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.id == slot_id).with_for_update()); attempt=session.scalar(select(SourceCorrectedExecutionAttempt).where(SourceCorrectedExecutionAttempt.attempt_id == attempt_id).with_for_update())
        if slot is None or attempt is None or slot.state != "RESERVED" or slot.execution_owner != owner: raise SourceCorrectedPreflightError("cannot record an unclaimed pre-send failure")
        now=utc_now(); slot.state,slot.final_outcome,slot.error_category,slot.completed_at,slot.execution_owner,slot.lease_expires_at="FAILED","MISSING_PASS","SOURCE_ASSERTION",now,None,None
        attempt.state,attempt.failure_category,attempt.retry_decision,attempt.completed_at="FAILED","SOURCE_ASSERTION","TERMINAL",now
        attempt.details_json={**(attempt.details_json or {}),"safe_reason":reason[:160]}; session.flush()

    def persist(self, session: Session, slot_id: Any, attempt_id: str, result: NormalizedEvaluationResult, *, owner: str,
                retry_policy: Callable[[str], Any] = retry_rule, retry_delay_seconds: int | None = None) -> str:
        slot = session.scalar(select(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.id == slot_id).with_for_update()); attempt = session.scalar(select(SourceCorrectedExecutionAttempt).where(SourceCorrectedExecutionAttempt.attempt_id == attempt_id).with_for_update())
        if slot is None or attempt is None or slot.state != "SENT" or slot.execution_owner != owner: raise SourceCorrectedPreflightError("response does not match a sent slot")
        actual = _actual_cost(slot.judge_id, result); now = utc_now(); attempt.input_tokens, attempt.output_tokens, attempt.actual_usd, attempt.provider_response_id = result.input_tokens, result.output_tokens, actual, result.provider_response_id
        metadata = {"parse_status": result.parse_status, "effective_model": result.effective_model, "model_version": result.model_version, "latency_ms": result.latency_ms, "criteria_scores": result.criterion_scores, "explanation": result.explanation, "route": result.route_provenance}
        slot.response_metadata_json, slot.actual_usd, slot.final_outcome, slot.error_category = metadata, actual, result.outcome.value, result.error_code
        if result.outcome in {Outcome.ANSWER_A, Outcome.ANSWER_B, Outcome.TIE, Outcome.UNKNOWN}:
            slot.state, attempt.state, attempt.retry_decision, slot.completed_at = "COMPLETED", "SUCCEEDED", "FINAL", now
        else:
            rule = retry_policy(result.error_code or "PROVIDER_ERROR")
            if rule.retryable and attempt.attempt_index < rule.max_retries:
                slot.state, attempt.state, attempt.retry_decision = "PENDING", "FAILED_RETRYABLE", "RETRY"
                if retry_delay_seconds:
                    slot.next_eligible_at = now + timedelta(seconds=retry_delay_seconds)
            else:
                slot.state, attempt.state, attempt.retry_decision, slot.completed_at = "FAILED", "FAILED", "TERMINAL", now
            attempt.failure_category = result.error_code or "PROVIDER_ERROR"
        attempt.details_json = {**(attempt.details_json or {}), "result": metadata}; attempt.completed_at, slot.execution_owner, slot.lease_expires_at = now, None, None; session.flush(); return slot.state

    def next_eligible_at(self, session: Session, batch: SourceCorrectedExecutionBatch) -> datetime | None:
        return session.scalar(select(func.min(SourceCorrectedExecutionSlot.next_eligible_at)).where(
            SourceCorrectedExecutionSlot.batch_id == batch.id,
            SourceCorrectedExecutionSlot.state == "PENDING",
            SourceCorrectedExecutionSlot.next_eligible_at.is_not(None),
        ))

    def status(self, session: Session, batch: SourceCorrectedExecutionBatch) -> dict[str, Any]:
        slots = list(session.scalars(select(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == batch.id)))
        attempt_pairs = list(session.execute(select(SourceCorrectedExecutionAttempt, SourceCorrectedExecutionSlot.provider).join(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == batch.id)))
        attempts = [row[0] for row in attempt_pairs]
        states, by_rq, by_judge = Counter(x.state for x in slots), Counter(), Counter()
        for row in slots:
            if row.state == "COMPLETED": by_rq[row.rq_code] += 1; by_judge[row.judge_id] += 1
        def used(provider: str | None = None) -> dict[str, str]:
            chosen = attempt_pairs if provider is None else [pair for pair in attempt_pairs if pair[1] == provider]
            actual = sum((Decimal(a.actual_usd or 0) for a, _ in chosen), Decimal("0"))
            reserved = sum((Decimal(a.reserved_usd) for a, _ in chosen if a.actual_usd is None), Decimal("0"))
            return {"actual": str(actual), "reserved": str(reserved), "total": str(actual + reserved)}
        next_ready = min((as_utc(slot.next_eligible_at) for slot in slots if slot.state == "PENDING" and slot.next_eligible_at), default=None)
        return {"planned": len(slots), "completed": states["COMPLETED"], "pending": states["PENDING"], "in_progress": states["RESERVED"] + states["SENT"], "failed": states["FAILED"], "ambiguous": states["AMBIGUOUS"], "attempts": len(attempts), "retries": sum(a.attempt_index > 0 for a in attempts), "per_rq": dict(by_rq), "per_judge": dict(by_judge), "spend": {"OPENAI": used("OPENAI"), "OPENROUTER": used("OPENROUTER"), "GLOBAL": used()}, "batch_status": batch.status, "last_event": _last_event(slots, attempts), "next_eligible_at": next_ready.isoformat() if next_ready else None}

    def finalize_if_exhausted(self, session: Session, batch: SourceCorrectedExecutionBatch) -> None:
        report = self.status(session, batch)
        if report["pending"] == report["in_progress"] == 0 and report["completed"] + report["failed"] + report["ambiguous"] == report["planned"]:
            batch.status = "COMPLETED"


def _actual_cost(judge: str, result: NormalizedEvaluationResult) -> Decimal | None:
    if result.provider_reported_cost is not None:
        try: return Decimal(str(result.provider_reported_cost))
        except Exception: pass
    if result.input_tokens is not None and result.output_tokens is not None:
        rate = price_for_model(judge); return Decimal(result.input_tokens) * rate.input_per_token + Decimal(result.output_tokens) * rate.output_per_token
    return None


def _last_event(slots: list[SourceCorrectedExecutionSlot], attempts: list[SourceCorrectedExecutionAttempt]) -> str:
    if not attempts: return "No provider attempt recorded."
    latest = max(attempts, key=lambda x: x.started_at); slot = next(x for x in slots if x.id == latest.slot_id)
    return f"{slot.judge_id} | {slot.rq_code} | {latest.state} | attempt {latest.attempt_index + 1}"


def render_dashboard(report: dict[str, Any], caps: dict[str, str], *, elapsed: float = 0.0, rate: float = 0.0) -> str:
    completed, planned = int(report["completed"]), int(report["planned"]); width = 24; filled = round(width * completed / planned) if planned else 0
    eta = "calculating..." if rate <= 0 else f"~{int((planned-completed)/rate//60):02d}:{int((planned-completed)/rate%60):02d}"
    rq_total = {"RQ1":229,"RQ2":2410,"RQ3":512,"RQ4":138,"RQ5":102,"RQ6":337,"RQ7_PRIMARY":729,"RQ7_SECONDARY":1992}
    judge_total={"gpt-4o-mini":1590,"anthropic/claude-3-haiku":1609,"deepseek/deepseek-chat":1595,"meta-llama/llama-3.3-70b-instruct":1655}
    lines = ["SOURCE-CORRECTED EXECUTION", "=" * 60, f"Overall [{'#'*filled}{'-'*(width-filled)}] {completed} / {planned} {100*completed/planned:5.1f}%", f"Completed {completed} | Pending {report['pending']} | In progress {report['in_progress']} | Failed {report['failed']} | Ambiguous {report['ambiguous']}", f"Attempts {report['attempts']} | Retries {report['retries']} | Elapsed {int(elapsed//60):02d}:{int(elapsed%60):02d} | Rate {rate*60:.1f} passes/min | ETA {eta}", "", "Per judge: " + " | ".join(f"{j}: {report['per_judge'].get(j,0)}/{judge_total[j]}" for j in judge_total), "Per RQ:"]
    lines += [f"{rq:14} {report['per_rq'].get(rq,0):4}/{total}" for rq,total in rq_total.items()]
    lines += ["", f"OpenAI     actual ${report['spend']['OPENAI']['actual']} + reserved ${report['spend']['OPENAI']['reserved']} / ${caps['OPENAI']}", f"OpenRouter actual ${report['spend']['OPENROUTER']['actual']} + reserved ${report['spend']['OPENROUTER']['reserved']} / ${caps['OPENROUTER']}", f"Global     actual ${report['spend']['GLOBAL']['actual']} + reserved ${report['spend']['GLOBAL']['reserved']} / ${caps['GLOBAL']}", "Last event: " + report["last_event"]]
    if report.get("stop_reason"):
        lines += ["EXECUTION STOPPED", "Reason: " + str(report["stop_reason"])]
    lines += ["=" * 60]
    return "\n".join(lines)


class MockTransport:
    is_mock = True
    def __init__(self) -> None: self.sent: list[str] = []
    def __call__(self, endpoint: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        self.sent.append(stable_sha(payload)); provider = payload.get("provider", {}).get("only", [None])[0]
        response = {"id": f"mock-{len(self.sent)}", "model": payload["model"], "usage": {"prompt_tokens": max(1, sum(len(x["content"]) for x in payload["messages"])//4), "completion_tokens": 20}, "choices": [{"message": {"content": json.dumps({"verdict":"TIE","criteria_scores":{"correctness":3,"relevance":3,"completeness":3,"clarity":3,"safety":3},"confidence":0.5,"explanation":"mock"})}}]}
        if provider: response["provider"] = {"provider_slug": provider}
        return response


class SourceCorrectedRunner:
    def __init__(self, session_factory: Callable[[], Session], *, transport: Transport | None = None) -> None:
        self.session_factory, self.transport, self.manifest = session_factory, transport, load_manifest(); self.rows = {x["planned_pass_id"]:x for x in self.manifest["planned_passes"]}; self.store = SourceCorrectedStore(); self.resolver = FrozenPayloadResolver(self.manifest)

    def batch(self, session: Session) -> SourceCorrectedExecutionBatch:
        batch = session.scalar(select(SourceCorrectedExecutionBatch).where(SourceCorrectedExecutionBatch.manifest_sha256 == self.manifest["manifest_sha256"]))
        if batch is None: raise SourceCorrectedPreflightError("corrected execution batch has not been materialized")
        if batch.reconciliation_sha256 != RECONCILIATION_SHA256: raise SourceCorrectedPreflightError("corrected batch reconciliation mismatch")
        return batch

    def status(self) -> tuple[dict[str, Any], dict[str, str]]:
        with self.session_factory() as session:
            batch = self.batch(session); return self.store.status(session, batch), {**batch.provider_hard_caps_json, "GLOBAL": str(batch.global_hard_cap_usd)}

    def reconcile_stale_in_flight(self) -> dict[str, Any]:
        """Fail closed for expired claims without evaluating a provider."""
        with self.session_factory() as session:
            batch = self.batch(session)
            self.store.recover(session, batch)
            self.store.finalize_if_exhausted(session, batch)
            report = self.store.status(session, batch)
            session.commit()
            return report

    def execute(self, *, confirmation: str, max_slots: int | None = None, progress: Callable[[dict[str, Any], dict[str,str], float, float], None] | None = None) -> dict[str, Any]:
        if confirmation != "I_CONFIRM_SOURCE_CORRECTED_PAID_EXECUTION": raise SourceCorrectedPreflightError("paid execution requires exact confirmation")
        if self.transport is None and not all(credentials_present().values()): raise SourceCorrectedPreflightError("provider credentials are missing")
        owner, started, done_at_start = uuid4().hex, monotonic(), 0
        with self.session_factory() as session:
            batch = self.batch(session); self.store.recover(session, batch); session.commit(); initial = self.store.status(session,batch); done_at_start = initial["completed"]
        processed = 0; last = monotonic()
        try:
            while max_slots is None or processed < max_slots:
                with self.session_factory() as session:
                    batch = self.batch(session); claimed = self.store.claim(session,batch,owner=owner); session.commit()
                    if claimed is None:
                        next_ready = self.store.next_eligible_at(session, batch)
                        if next_ready is not None:
                            wait = max(0.0, (as_utc(next_ready) - utc_now()).total_seconds())
                            session.commit()
                            if wait:
                                sleep(wait)
                            continue
                        self.store.finalize_if_exhausted(session,batch); report=self.store.status(session,batch); session.commit(); break
                    slot, attempt = claimed; slot_id, attempt_id, attempt_index = slot.id, attempt.attempt_id, attempt.attempt_index
                try:
                    with self.session_factory() as session:
                        batch=self.batch(session); slot=session.get(SourceCorrectedExecutionSlot,slot_id)
                        try: row,request=self.resolver.payload(session,slot)
                        except SourceCorrectedPreflightError as exc:
                            self.store.fail_before_send(session,slot_id,attempt_id,owner=owner,reason=str(exc)); session.commit(); raise
                        self.store.mark_sent(session,slot_id,attempt_id,owner=owner); session.commit()
                    result=self._evaluate(row,request)
                    with self.session_factory() as session: state=self.store.persist(session,slot_id,attempt_id,result,owner=owner); batch=self.batch(session); session.commit()
                    if state == "PENDING":
                        delay = next_backoff_seconds(result.error_code or "PROVIDER_ERROR", attempt_index)
                        if delay: sleep(delay)
                except SourceCorrectedPreflightError:
                    raise
                processed += 1
                if progress and (processed % 10 == 0 or monotonic()-last > 1):
                    report,caps = self.status(); elapsed=monotonic()-started; rate=(report["completed"]-done_at_start)/elapsed if elapsed else 0
                    if progress: progress(report,caps,elapsed,rate)
                    last=monotonic()
            report, caps = self.status()
            if progress: progress(report,caps,monotonic()-started,(report["completed"]-done_at_start)/max(monotonic()-started,0.001))
            return report
        except KeyboardInterrupt:
            report,caps=self.status()
            report["stop_reason"] = "INTERRUPTED"
            if progress: progress(report,caps,monotonic()-started,(report["completed"]-done_at_start)/max(monotonic()-started,0.001))
            print("EXECUTION STOPPED\nReason: INTERRUPTED", file=sys.stderr)
            return report
        except Exception as exc:
            # Do not alter a durable SENT attempt here: without a persisted
            # response it must later be explicitly reconciled as AMBIGUOUS.
            report, caps = self.status()
            if isinstance(exc, SourceCorrectedPreflightError):
                reason = f"SOURCE_INVARIANT: {str(exc)[:160]}"
            elif isinstance(exc, SQLAlchemyError):
                reason = "DATABASE_PERSISTENCE_ERROR"
            else:
                reason = f"UNEXPECTED_EXECUTOR_ERROR: {type(exc).__name__}"
            report["stop_reason"] = reason
            if progress: progress(report,caps,monotonic()-started,(report["completed"]-done_at_start)/max(monotonic()-started,0.001))
            print(f"EXECUTION STOPPED\nReason: {reason}", file=sys.stderr)
            return report

    def _evaluate(self, row: dict[str, Any], request: EvaluationRequest) -> NormalizedEvaluationResult:
        spec=MODEL_REGISTRY[row["judge_id"]]; gate=ProviderExecutionGate(mode="REAL",authorization_token="source-corrected-explicit",verified_pricing_version=PRICING_CONFIG["version"],max_provider_calls=TOTAL,max_input_tokens=10**9,max_output_tokens=TOTAL*350,max_usd=float(self.manifest["budget_metadata"]["global_hard_cap_usd"]))
        return ControlledEvaluationEngine(adapter_for_judge(spec.judge_name,transport=self.transport or environment_http_transport,gate=gate)).evaluate(request)

    def execute_mock_full(self) -> dict[str, Any]:
        """Fast provider-free whole-manifest rehearsal using the same ledger,
        frozen payload assertions, adapter/parser, reservations and completion
        transitions in one disposable test transaction."""
        if not isinstance(self.transport, MockTransport): raise SourceCorrectedPreflightError("full rehearsal requires MockTransport")
        owner = "mock-full"
        with self.session_factory() as session:
            batch=self.batch(session); self.store.recover(session,batch)
            # The dedicated rehearsal keeps one transaction for speed, while
            # validating every frozen payload through the exact adapter/parser
            # and recording the same RESERVED -> SENT -> COMPLETED ledger
            # sequence.  Production uses the per-send committed path above.
            slots=list(session.scalars(select(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == batch.id, SourceCorrectedExecutionSlot.state == "PENDING").order_by(SourceCorrectedExecutionSlot.planned_pass_id)))
            with session.no_autoflush:
                for slot in slots:
                    row,request=self.resolver.payload(session,slot); index=slot.attempt_count
                    forecast=Decimal(slot.estimated_input_tokens)*price_for_model(slot.judge_id).input_per_token+Decimal(slot.estimated_output_tokens)*price_for_model(slot.judge_id).output_per_token
                    attempt=SourceCorrectedExecutionAttempt(slot_id=slot.id,attempt_id=stable_sha({"slot":slot.planned_pass_id,"attempt":index}),attempt_index=index,state="RESERVED",reserved_usd=forecast,details_json={"owner":owner,"mock":True})
                    slot.state,slot.attempt_count,slot.execution_owner="RESERVED",index+1,owner; session.add(attempt); slot.state,attempt.state="SENT","SENT"
                    result=self._evaluate(row,request); actual=_actual_cost(slot.judge_id,result); now=utc_now()
                    attempt.state,attempt.retry_decision,attempt.input_tokens,attempt.output_tokens,attempt.actual_usd,attempt.completed_at="SUCCEEDED","FINAL",result.input_tokens,result.output_tokens,actual,now
                    slot.state,slot.final_outcome,slot.actual_usd,slot.completed_at,slot.execution_owner,slot.lease_expires_at="COMPLETED",result.outcome.value,actual,now,None,None
            self.store.finalize_if_exhausted(session,batch); report=self.store.status(session,batch); session.commit(); return report
