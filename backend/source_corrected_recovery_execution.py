"""Durable, additive executor for the frozen 119-slot source-corrected recovery.

This module deliberately shares the corrected-execution ledger, parser and
provider adapters.  It creates a separate batch whose slots retain immutable
links to their original failed/ambiguous logical slots; it never updates the
parent batch or Phase 11 evidence.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from datetime import timedelta
from decimal import Decimal
from time import monotonic, sleep
from types import SimpleNamespace
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from build_source_corrected_recovery_amendment import (AMENDMENT_IDENTITY, AMENDMENT_PATH,
                                                       RECOVERY_MANIFEST_IDENTITY, RECOVERY_MANIFEST_PATH)
from controlled_evaluation import ControlledEvaluationEngine, EvaluationRequest, NormalizedEvaluationResult
from controlled_providers import ProviderExecutionGate, Transport, adapter_for_judge, environment_http_transport
from execution_policy import RetryRule
from model_registry import MODEL_REGISTRY
from pricing import CONFIG as PRICING_CONFIG
from source_corrected_execution import SourceCorrectedPreflightError, stable_sha
from source_corrected_execution_models import (SourceCorrectedExecutionAttempt,
                                               SourceCorrectedExecutionBatch,
                                               SourceCorrectedExecutionSlot)
from source_corrected_real_execution import (MockTransport, SourceCorrectedStore,
                                             FrozenPayloadResolver, _actual_cost, as_utc,
                                             credentials_present, render_dashboard, utc_now)


TOTAL = 119
CONFIRMATION = "I_CONFIRM_SOURCE_CORRECTED_RECOVERY_PAID_EXECUTION"
AMENDMENT_SHA = "22a60b7ca5075eb5d53864274205756ba3bdd31d9b3887ae79a17fba690683eb"
RECOVERY_MANIFEST_SHA = "2fd7b64246cfba8421dc3d714fc272cef65214ecef1286c96318d0e65adc663d"
RECOVERY_POLICY_IDENTITY = "source-corrected-recovery-retry-v1"
logger = logging.getLogger(__name__)


def _read_verified_artifacts() -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = json.loads(RECOVERY_MANIFEST_PATH.read_text(encoding="utf-8"))
    amendment = json.loads(AMENDMENT_PATH.read_text(encoding="utf-8"))
    for payload, field, expected, identity_field, identity in (
        (manifest, "recovery_manifest_sha256", RECOVERY_MANIFEST_SHA, "recovery_manifest_identity", RECOVERY_MANIFEST_IDENTITY),
        (amendment, "amendment_sha256", AMENDMENT_SHA, "amendment_identity", AMENDMENT_IDENTITY),
    ):
        claimed = payload.pop(field, None)
        try:
            if claimed != expected or stable_sha(payload) != expected or payload.get(identity_field) != identity:
                raise SourceCorrectedPreflightError("frozen recovery artifact identity/SHA mismatch")
        finally:
            payload[field] = claimed
    if amendment.get("recovery_manifest", {}).get("sha256") != RECOVERY_MANIFEST_SHA:
        raise SourceCorrectedPreflightError("amendment does not pin recovery manifest")
    rows = manifest.get("recovery_slots", [])
    counts = manifest.get("counts", {})
    if len(rows) != TOTAL or counts.get("total_recovery_slots") != TOTAL or counts.get("completed_slot_overlap") != 0:
        raise SourceCorrectedPreflightError("recovery count/overlap invariant failed")
    if len({row.get("recovery_slot_id") for row in rows}) != TOTAL or len({row.get("recovery_idempotency_key") for row in rows}) != TOTAL:
        raise SourceCorrectedPreflightError("recovery identity collision")
    if Counter(row.get("historical_terminal_state") for row in rows) != {"FAILED": 118, "AMBIGUOUS": 1}:
        raise SourceCorrectedPreflightError("recovery terminal-lineage population mismatch")
    if any(row.get("historical_terminal_state") not in {"FAILED", "AMBIGUOUS"} for row in rows):
        raise SourceCorrectedPreflightError("completed historical work is replayable")
    return manifest, amendment


def recovery_retry_rule(category: str) -> RetryRule:
    policy = {
        "RATE_LIMIT": (2, (120, 300)),
        "TEMPORARY_5XX": (2, (60, 180)),
        "NETWORK_CONNECTION": (2, (60, 180)),
        "CONNECTION": (2, (60, 180)),
        "TIMEOUT": (1, (60,)),
        "INVALID_RESPONSE": (1, (30,)),
    }
    retries, _ = policy.get(category, (0, ()))
    return RetryRule(retryable=retries > 0, max_retries=retries)


def recovery_backoff_seconds(category: str, attempt_index: int) -> int:
    values = {
        "RATE_LIMIT": (120, 300), "TEMPORARY_5XX": (60, 180),
        "NETWORK_CONNECTION": (60, 180), "CONNECTION": (60, 180),
        "TIMEOUT": (60,), "INVALID_RESPONSE": (30,),
    }.get(category, ())
    return values[min(attempt_index, len(values) - 1)] if values else 0


class RecoveryPayloadResolver:
    """Resolves recovery text through the parent frozen payload implementation.

    The small proxy uses the parent manifest key only for its immutable source
    assertions.  The resulting request is then bound to the *new* recovery
    slot UUID and recovery-manifest provenance.
    """
    def __init__(self, recovery_manifest: dict[str, Any]) -> None:
        from source_corrected_real_execution import load_manifest
        self.rows = {row["recovery_slot_id"]: row for row in recovery_manifest["recovery_slots"]}
        self.parent = FrozenPayloadResolver(load_manifest())
        self.parent_rows = self.parent.rows

    def payload(self, session: Session, slot: SourceCorrectedExecutionSlot) -> tuple[dict[str, Any], EvaluationRequest]:
        row = self.rows.get(slot.planned_pass_id)
        if row is None:
            raise SourceCorrectedPreflightError("recovery slot is absent from frozen recovery manifest")
        expected = {
            "recovery_manifest_sha256": RECOVERY_MANIFEST_SHA,
            "original_logical_slot_id": row["original_logical_slot_id"],
            "original_planned_pass_id": row["original_planned_pass_id"],
            "recovery_reason": row["recovery_reason"],
            "payload_sha256": row["rendered_payload_sha256"],
            "idempotency_key": row["recovery_idempotency_key"],
            "rq_code": row["rq_code"], "judge_id": row["judge_id"],
            "provider": row["provider"], "route": row["route"],
            "condition_code": row["condition_code"], "presentation": row["presentation"],
            "corrected_record_key": row["corrected_record_key"],
        }
        actual = {
            "recovery_manifest_sha256": slot.recovery_manifest_sha256,
            "original_logical_slot_id": str(slot.original_logical_slot_id) if slot.original_logical_slot_id else None,
            "original_planned_pass_id": slot.original_planned_pass_id,
            "recovery_reason": slot.recovery_reason, "payload_sha256": slot.payload_sha256,
            "idempotency_key": slot.idempotency_key, "rq_code": slot.rq_code,
            "judge_id": slot.judge_id, "provider": slot.provider, "route": slot.route,
            "condition_code": slot.condition_code, "presentation": slot.presentation,
            "corrected_record_key": slot.corrected_record_key,
        }
        if actual != expected:
            raise SourceCorrectedPreflightError("durable recovery slot provenance/configuration mismatch")
        expected_lineage = recovery_lineage(row, self.parent_rows.get(row["original_planned_pass_id"]))
        if slot.recovery_lineage_json != expected_lineage:
            raise SourceCorrectedPreflightError("durable recovery source/prompt lineage mismatch")
        parent_row = self.parent_rows.get(row["original_planned_pass_id"])
        if parent_row is None or any(parent_row.get(key) != row.get(key) for key in (
            "corrected_dataset_version", "corrected_record_key", "rendered_payload_sha256", "source_corrected_payload",
            "prompt_id", "prompt_sha256", "prompt_template_version", "prompt_template_sha256", "judge_id", "provider",
            "provider_model", "route", "routing_policy_version", "routing_fingerprint", "temperature", "top_p", "seed",
            "rq_code", "condition_code", "presentation", "repetition_index", "transform",
        )):
            raise SourceCorrectedPreflightError("recovery row diverges from its frozen parent configuration")
        proxy = SimpleNamespace(planned_pass_id=parent_row["planned_pass_id"], payload_sha256=parent_row["rendered_payload_sha256"],
                                idempotency_key=parent_row["idempotency_key"], id=slot.id)
        _parent_row, request = self.parent.payload(session, proxy)
        return row, request.model_copy(update={"presentation_provenance": {
            "source_corrected_manifest": RECOVERY_MANIFEST_IDENTITY,
            "recovery_manifest_sha256": RECOVERY_MANIFEST_SHA,
            "original_logical_slot_id": str(slot.original_logical_slot_id),
            "original_planned_pass_id": slot.original_planned_pass_id,
            "recovery_reason": slot.recovery_reason,
            "payload_sha256": slot.payload_sha256,
            "transform": row.get("transform"),
        }})


def recovery_lineage(row: dict[str, Any], parent_row: dict[str, Any] | None) -> dict[str, Any]:
    """Persist source identity from the pinned parent manifest when the
    recovery amendment intentionally stores only its rendered payload hashes."""
    if parent_row is None:
        raise SourceCorrectedPreflightError("recovery row has no frozen parent lineage")
    return {
        "historical_terminal_state": row.get("historical_terminal_state"),
        "historical_final_outcome": row.get("historical_final_outcome"),
        "historical_failure_category": row.get("historical_failure_category"),
        "historical_attempt_lineage": row.get("historical_attempt_lineage"),
        "corrected_dataset_version": row.get("corrected_dataset_version"),
        "source_corrected_payload": row.get("source_corrected_payload"),
        "source_question_id": parent_row.get("source_question_id"),
        "source_turn": parent_row.get("source_turn"),
        "corrected_source_answer_hashes": parent_row.get("corrected_source_answer_hashes"),
        "prompt_id": row.get("prompt_id"), "prompt_sha256": row.get("prompt_sha256"),
        "prompt_template_version": row.get("prompt_template_version"),
        "prompt_template_sha256": row.get("prompt_template_sha256"),
        "provider_model": row.get("provider_model"), "routing_policy_version": row.get("routing_policy_version"),
        "routing_fingerprint": row.get("routing_fingerprint"), "temperature": row.get("temperature"),
        "top_p": row.get("top_p"), "seed": row.get("seed"), "repetition_index": row.get("repetition_index"),
        "transform": row.get("transform"),
    }


def render_recovery_dashboard(report: dict[str, Any], caps: dict[str, str], *, elapsed: float = 0.0, rate: float = 0.0) -> str:
    text = render_dashboard(report, caps, elapsed=elapsed, rate=rate)
    text = text.replace("SOURCE-CORRECTED EXECUTION", "SOURCE-CORRECTED RECOVERY")
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("Per judge:"):
            lines[index] = "Per judge: " + " | ".join(f"{name}: {report['per_judge'].get(name, 0)}/{total}" for name, total in {
                "gpt-4o-mini": 1, "anthropic/claude-3-haiku": 23,
                "deepseek/deepseek-chat": 86, "meta-llama/llama-3.3-70b-instruct": 9,
            }.items())
        if line.startswith("RQ1") or line.startswith("RQ2") or line.startswith("RQ3") or line.startswith("RQ4") or line.startswith("RQ5") or line.startswith("RQ6") or line.startswith("RQ7"):
            totals = {"RQ1": 4, "RQ2": 53, "RQ3": 10, "RQ4": 6, "RQ5": 0, "RQ6": 0, "RQ7_PRIMARY": 11, "RQ7_SECONDARY": 35}
            code = line.split()[0]
            if code in totals:
                lines[index] = f"{code:14} {report['per_rq'].get(code, 0):4}/{totals[code]}"
    if report.get("next_eligible_at"):
        lines.insert(-1, "Next retry eligible: " + report["next_eligible_at"])
    used = Decimal(report["spend"]["GLOBAL"]["total"])
    hard_cap = Decimal(caps["GLOBAL"])
    lines.insert(-1, "Expected $0.0522640002 | P90 + 15% $0.08286308 | Recovery hard cap $0.15679201")
    lines.insert(-1, f"Recovery headroom ${hard_cap - used} | Provider expected: OpenAI $0.00025185 | OpenRouter $0.0520121502")
    return "\n".join(lines)


class SourceCorrectedRecoveryRunner:
    def __init__(self, session_factory: Callable[[], Session], *, transport: Transport | None = None,
                 sleep_fn: Callable[[float], None] = sleep) -> None:
        self.session_factory, self.transport, self.sleep_fn = session_factory, transport, sleep_fn
        self.manifest, self.amendment = _read_verified_artifacts()
        self.store, self.resolver = SourceCorrectedStore(), RecoveryPayloadResolver(self.manifest)

    def batch(self, session: Session) -> SourceCorrectedExecutionBatch:
        batch = session.scalar(select(SourceCorrectedExecutionBatch).where(
            SourceCorrectedExecutionBatch.manifest_sha256 == RECOVERY_MANIFEST_SHA))
        if batch is None:
            raise SourceCorrectedPreflightError("recovery batch has not been materialized; run --preflight")
        if batch.manifest_identity != RECOVERY_MANIFEST_IDENTITY or batch.provenance_json.get("execution_class") != "SOURCE_CORRECTED_RECOVERY":
            raise SourceCorrectedPreflightError("recovery batch identity/provenance mismatch")
        return batch

    def materialize(self, session: Session) -> SourceCorrectedExecutionBatch:
        parent_sha = self.manifest["parent_corrected_manifest"]["sha256"]
        parent = session.scalar(select(SourceCorrectedExecutionBatch).where(SourceCorrectedExecutionBatch.manifest_sha256 == parent_sha))
        if parent is None or parent.status != "COMPLETED":
            raise SourceCorrectedPreflightError("parent corrected batch is not terminally completed")
        batch = session.scalar(select(SourceCorrectedExecutionBatch).where(SourceCorrectedExecutionBatch.manifest_sha256 == RECOVERY_MANIFEST_SHA))
        caps = self.manifest["budget"]["bounded_retry_hard_cap_usd"]
        if batch is None:
            batch = SourceCorrectedExecutionBatch(
                dataset_version_id=parent.dataset_version_id, reconciliation_sha256=parent.reconciliation_sha256,
                manifest_identity=RECOVERY_MANIFEST_IDENTITY, manifest_sha256=RECOVERY_MANIFEST_SHA,
                global_hard_cap_usd=Decimal(self.manifest["budget"]["bounded_retry_hard_cap_total_usd"]),
                provider_hard_caps_json=caps, status="MATERIALIZED", provenance_json={
                    "execution_class": "SOURCE_CORRECTED_RECOVERY", "recovery_manifest_sha256": RECOVERY_MANIFEST_SHA,
                    "amendment_sha256": AMENDMENT_SHA, "parent_batch_id": str(parent.id),
                    "parent_manifest_sha256": parent_sha, "retry_policy_identity": RECOVERY_POLICY_IDENTITY,
                    "global_concurrency": 1,
                })
            session.add(batch); session.flush()
        elif batch.global_hard_cap_usd != Decimal(self.manifest["budget"]["bounded_retry_hard_cap_total_usd"]) or batch.provider_hard_caps_json != caps:
            raise SourceCorrectedPreflightError("existing recovery batch budget differs from frozen manifest")
        existing = {slot.planned_pass_id: slot for slot in session.scalars(select(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == batch.id))}
        parent_slots = {str(slot.id): slot for slot in session.scalars(select(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == parent.id))}
        parent_completed = {slot.planned_pass_id for slot in parent_slots.values() if slot.state == "COMPLETED"}
        for row in self.manifest["recovery_slots"]:
            original = parent_slots.get(row["original_logical_slot_id"])
            if original is None or original.planned_pass_id != row["original_planned_pass_id"] or original.state not in {"FAILED", "AMBIGUOUS"}:
                raise SourceCorrectedPreflightError("recovery original slot is not the frozen terminal parent slot")
            if row["original_planned_pass_id"] in parent_completed:
                raise SourceCorrectedPreflightError("recovery overlaps completed historical corrected work")
            slot = existing.get(row["recovery_slot_id"])
            values = dict(
                batch_id=batch.id, planned_pass_id=row["recovery_slot_id"], idempotency_key=row["recovery_idempotency_key"],
                rq_code=row["rq_code"], condition_code=row["condition_code"], judge_id=row["judge_id"], provider=row["provider"],
                requested_model=row.get("provider_model") or MODEL_REGISTRY[row["judge_id"]].requested_model, route=row["route"],
                presentation=row["presentation"], corrected_record_key=row["corrected_record_key"], payload_sha256=row["rendered_payload_sha256"],
                estimated_input_tokens=row["estimated_input_tokens"], estimated_output_tokens=row["estimated_output_tokens"],
                recovery_manifest_sha256=RECOVERY_MANIFEST_SHA, original_logical_slot_id=original.id,
                original_planned_pass_id=original.planned_pass_id, recovery_reason=row["recovery_reason"],
                recovery_lineage_json=recovery_lineage(row, self.resolver.parent_rows.get(row["original_planned_pass_id"])),
            )
            if slot is None:
                session.add(SourceCorrectedExecutionSlot(**values, state="PENDING"))
            else:
                immutable = {key: value for key, value in values.items()
                             if key not in {"batch_id", "recovery_lineage_json"}}
                if any(getattr(slot, key) != value for key, value in immutable.items()):
                    raise SourceCorrectedPreflightError("existing recovery slot differs from frozen manifest")
                # The first preflight preceding this forward-only field could
                # only have created untouched PENDING rows.  Fill that missing
                # metadata once; never rewrite an attempted recovery slot.
                if slot.state == "PENDING" and slot.attempt_count == 0:
                    slot.recovery_lineage_json = values["recovery_lineage_json"]
                elif slot.recovery_lineage_json != values["recovery_lineage_json"]:
                    raise SourceCorrectedPreflightError("existing recovery lineage differs from frozen manifest")
        session.flush()
        materialized = list(session.scalars(select(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == batch.id)))
        if len(materialized) != TOTAL or len({slot.planned_pass_id for slot in materialized}) != TOTAL:
            raise SourceCorrectedPreflightError("recovery materialization has an unexpected slot count")
        return batch

    def preflight(self) -> dict[str, Any]:
        with self.session_factory() as session:
            batch = self.materialize(session)
            self.store.recover(session, batch)
            slots = list(session.scalars(select(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == batch.id)))
            if len(slots) != TOTAL or any(slot.recovery_manifest_sha256 != RECOVERY_MANIFEST_SHA for slot in slots):
                raise SourceCorrectedPreflightError("recovery materialization/integrity check failed")
            report = self.store.status(session, batch)
            # A provider-free abort before any SENT transition restores the
            # batch to its explicit pre-execution state, rather than leaving a
            # misleading RUNNING label with no in-flight work.
            if report["pending"] == TOTAL and report["in_progress"] == report["completed"] == report["failed"] == report["ambiguous"] == 0:
                batch.status = "MATERIALIZED"
                session.flush()
                report = self.store.status(session, batch)
            batch_id = str(batch.id)
            session.commit()
        return {"status": "READY", "batch_id": batch_id, "slots": TOTAL, "overlap": 0,
                "credentials_present": credentials_present(), "hard_cap_usd": str(self.manifest["budget"]["bounded_retry_hard_cap_total_usd"]),
                "report": report, "provider_calls": 0}

    def status(self) -> tuple[dict[str, Any], dict[str, str]]:
        with self.session_factory() as session:
            batch = self.batch(session)
            return self.store.status(session, batch), {**batch.provider_hard_caps_json, "GLOBAL": str(batch.global_hard_cap_usd)}

    def reconcile_stale_in_flight(self) -> dict[str, Any]:
        with self.session_factory() as session:
            batch = self.batch(session)
            self.store.recover(session, batch)
            self.store.finalize_if_exhausted(session, batch)
            report = self.store.status(session, batch)
            session.commit()
            return report

    def abort_proven_pretransport_reservation(self, slot_id: Any) -> dict[str, Any]:
        """Operator-safe diagnostic recovery; never crosses a provider boundary."""
        with self.session_factory() as session:
            batch = self.batch(session)
            self.store.abort_reserved_before_transport(
                session, batch, slot_id, reason="DATABASE_PERSISTENCE_FAILURE_BEFORE_SENT",
            )
            self.store.finalize_if_exhausted(session, batch)
            report = self.store.status(session, batch)
            session.commit()
            return report

    def _pace_deepseek(self, session: Session, batch: SourceCorrectedExecutionBatch, slot: SourceCorrectedExecutionSlot) -> None:
        if slot.judge_id != "deepseek/deepseek-chat":
            return
        latest = session.scalar(select(SourceCorrectedExecutionAttempt.started_at).join(SourceCorrectedExecutionSlot).where(
            SourceCorrectedExecutionSlot.batch_id == batch.id,
            SourceCorrectedExecutionSlot.judge_id == "deepseek/deepseek-chat",
            SourceCorrectedExecutionAttempt.state.in_(("SENT", "SUCCEEDED", "FAILED", "AMBIGUOUS")),
        ).order_by(SourceCorrectedExecutionAttempt.started_at.desc()))
        if latest:
            remaining = 30.0 - (utc_now() - as_utc(latest)).total_seconds()
            if remaining > 0:
                self.sleep_fn(remaining)

    def execute(self, *, confirmation: str, max_slots: int | None = None,
                progress: Callable[[dict[str, Any], dict[str, str], float, float], None] | None = None) -> dict[str, Any]:
        if confirmation != CONFIRMATION:
            raise SourceCorrectedPreflightError("paid recovery execution requires exact confirmation")
        if self.transport is None and not all(credentials_present().values()):
            raise SourceCorrectedPreflightError("provider credentials are missing")
        owner, started, processed = uuid4().hex, monotonic(), 0
        stage = "startup_reconciliation"
        with self.session_factory() as session:
            batch = self.batch(session)
            self.store.recover(session, batch)
            session.commit()
        try:
            while max_slots is None or processed < max_slots:
                with self.session_factory() as session:
                    stage = "reserve_slot"
                    batch = self.batch(session)
                    claimed = self.store.claim(session, batch, owner=owner)
                    if claimed is None:
                        next_ready = self.store.next_eligible_at(session, batch)
                        if next_ready is None:
                            self.store.finalize_if_exhausted(session, batch)
                            report = self.store.status(session, batch)
                            session.commit()
                            break
                        wait = max(0.0, (as_utc(next_ready) - utc_now()).total_seconds())
                        session.commit()
                        if wait:
                            self.sleep_fn(wait)
                        continue
                    # SessionLocal expires objects on commit.  Preserve the
                    # durable identifiers while this transaction is live; the
                    # next transaction must never dereference detached ORM
                    # instances before it reaches the SENT boundary.
                    slot, attempt = claimed
                    slot_id, attempt_id, attempt_index = slot.id, attempt.attempt_id, attempt.attempt_index
                    session.commit()
                with self.session_factory() as session:
                    stage = "frozen_payload_resolution"
                    batch = self.batch(session)
                    slot = session.get(SourceCorrectedExecutionSlot, slot_id)
                    try:
                        row, request = self.resolver.payload(session, slot)
                    except SourceCorrectedPreflightError as exc:
                        self.store.fail_before_send(session, slot_id, attempt_id, owner=owner, reason=str(exc))
                        session.commit()
                        raise
                    stage = "deepseek_pacing"
                    self._pace_deepseek(session, batch, slot)
                    stage = "sent_transition"
                    self.store.mark_sent(session, slot_id, attempt_id, owner=owner)
                    session.commit()
                stage = "provider_transport"
                result = self._evaluate(row, request)
                with self.session_factory() as session:
                    stage = "response_persistence"
                    delay = recovery_backoff_seconds(result.error_code or "PROVIDER_ERROR", attempt_index)
                    self.store.persist(session, slot_id, attempt_id, result, owner=owner,
                                       retry_policy=recovery_retry_rule, retry_delay_seconds=delay)
                    session.commit()
                processed += 1
                if progress:
                    report, caps = self.status()
                    progress(report, caps, monotonic() - started, processed / max(monotonic() - started, .001))
            report, caps = self.status()
            if progress:
                progress(report, caps, monotonic() - started, processed / max(monotonic() - started, .001))
            return report
        except KeyboardInterrupt:
            report, caps = self.status(); report["stop_reason"] = "INTERRUPTED"
            if progress: progress(report, caps, monotonic() - started, 0)
            return report
        except Exception as exc:
            report, caps = self.status()
            if isinstance(exc, SQLAlchemyError):
                logger.exception("RECOVERY_DATABASE_PERSISTENCE_ERROR stage=%s", stage)
            report["stop_reason"] = (f"SOURCE_INVARIANT: {str(exc)[:160]}" if isinstance(exc, SourceCorrectedPreflightError)
                                     else "DATABASE_PERSISTENCE_ERROR" if isinstance(exc, SQLAlchemyError)
                                     else f"UNEXPECTED_EXECUTOR_ERROR: {type(exc).__name__}")
            if progress: progress(report, caps, monotonic() - started, 0)
            print("RECOVERY EXECUTION STOPPED\nReason: " + report["stop_reason"], file=sys.stderr)
            return report

    def _evaluate(self, row: dict[str, Any], request: EvaluationRequest) -> NormalizedEvaluationResult:
        spec = MODEL_REGISTRY[row["judge_id"]]
        gate = ProviderExecutionGate(mode="REAL", authorization_token="source-corrected-recovery-explicit",
                                     verified_pricing_version=PRICING_CONFIG["version"], max_provider_calls=TOTAL * 3,
                                     max_input_tokens=10**9, max_output_tokens=TOTAL * 3 * 350,
                                     max_usd=float(self.manifest["budget"]["bounded_retry_hard_cap_total_usd"]))
        return ControlledEvaluationEngine(adapter_for_judge(spec.judge_name, transport=self.transport or environment_http_transport, gate=gate)).evaluate(request)

    def execute_mock_full(self) -> dict[str, Any]:
        """Run all 119 slots through this same executor path using only MockTransport.

        This is deliberately available only to isolated test databases.  It
        exercises the production reservation/send/parser/persist transitions,
        while its injected no-op sleep keeps the rehearsal provider-free and
        fast.
        """
        if not isinstance(self.transport, MockTransport):
            raise SourceCorrectedPreflightError("full recovery rehearsal requires MockTransport")
        return self.execute(confirmation=CONFIRMATION)


def _print_progress(report: dict[str, Any], caps: dict[str, str], elapsed: float, rate: float) -> None:
    print(render_recovery_dashboard(report, caps, elapsed=elapsed, rate=rate))


def main() -> int:
    parser = argparse.ArgumentParser(description="Source-corrected additive recovery executor")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-paid-recovery")
    args = parser.parse_args()
    from database import SessionLocal
    runner = SourceCorrectedRecoveryRunner(SessionLocal)
    if args.preflight:
        print(json.dumps(runner.preflight(), sort_keys=True, default=str)); return 0
    if args.status:
        report, caps = runner.status(); print(render_recovery_dashboard(report, caps)); return 0
    if args.execute:
        report = runner.execute(confirmation=args.confirm_paid_recovery or "", progress=_print_progress)
        return 0 if not report.get("stop_reason") else 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
