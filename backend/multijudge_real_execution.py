"""Fail-closed, durable executor for the frozen multi-judge manifest.

Normal use is provider-free preflight.  Provider transport is reachable only
through the CLI's explicit paid-run confirmation, after a manifest-bound,
PostgreSQL-backed reservation has been committed.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from time import monotonic
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from build_multijudge_execution_manifest import _copy_rows
from controlled_evaluation import ControlledEvaluationEngine, EvaluationRequest, NormalizedEvaluationResult
from controlled_persistence import Outcome
from controlled_providers import ProviderExecutionGate, Transport, adapter_for_judge, environment_http_transport
from execution_policy import FAILURE_POLICY_VERSION, RETRY_POLICY_VERSION, retry_rule
from model_registry import MODEL_REGISTRY, Provider
from multijudge_execution_models import MultiJudgeExecutionAttempt, MultiJudgeExecutionBatch, MultiJudgeExecutionSlot
from pricing import CONFIG as PRICING_CONFIG, price_for_model
from routing_policy import routing_config, routing_fingerprint, routing_policy_version


ROOT = Path(__file__).resolve().parent.parent
PROTOCOL_PATH = ROOT / "evidence" / "multijudge_consensus" / "protocol_v1.json"
MANIFEST_PATH = ROOT / "evidence" / "multijudge_consensus" / "execution_manifest_v1.json"
EXPECTED_PROTOCOL_SHA256 = "819f2e2dea8fb32e4c32000551d6048a16ecc8d28f1bb32d2cce4d02a15c40ce"
EXPECTED_MANIFEST_SHA256 = "6c2fa4a926e458c598c73604daa1b69d766bc5b2d04853e73c3a35bf9017e351"
EXPECTED_JUDGES = (
    "gpt-4o-mini",
    "anthropic/claude-3-haiku",
    "deepseek/deepseek-chat",
    "meta-llama/llama-3.3-70b-instruct",
)
HARD_CAP_USD = Decimal("2.50")
PAID_CONFIRMATION = "I_CONFIRM_MULTI_JUDGE_PAID_EXECUTION"
LEASE_SECONDS = 300


class MultiJudgePreflightError(PermissionError):
    pass


@dataclass(frozen=True)
class FrozenMultiJudgeManifest:
    protocol: dict[str, Any]
    manifest: dict[str, Any]
    protocol_sha256: str
    manifest_sha256: str

    @property
    def judges(self) -> dict[str, dict[str, Any]]:
        return {row["judge_id"]: row for row in self.manifest["scientific_configuration"]["judges"]}

    @property
    def pairs(self) -> dict[str, dict[str, Any]]:
        return {row["canonical_pair_id"]: row for row in self.manifest["pairs"]}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def credential_presence() -> dict[str, bool]:
    """Only presence is observable; caller must never receive secret values."""
    return {
        "openai": bool(os.getenv("OPENAI_API_KEY", "").strip()),
        "openrouter": bool(os.getenv("OPENROUTER_API_KEY", "").strip()),
    }


def load_frozen_manifest() -> FrozenMultiJudgeManifest:
    protocol_sha, manifest_sha = _sha256(PROTOCOL_PATH), _sha256(MANIFEST_PATH)
    if protocol_sha != EXPECTED_PROTOCOL_SHA256 or manifest_sha != EXPECTED_MANIFEST_SHA256:
        raise MultiJudgePreflightError("frozen protocol or manifest SHA mismatch")
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    frozen = FrozenMultiJudgeManifest(protocol, manifest, protocol_sha, manifest_sha)
    if protocol.get("protocol_id") != "multi-judge-consensus-v1" or manifest.get("protocol_id") != protocol.get("protocol_id"):
        raise MultiJudgePreflightError("unexpected frozen protocol identity")
    if manifest.get("execution_authorized") is not False:
        raise MultiJudgePreflightError("frozen manifest must remain unauthorized")
    passes = manifest.get("planned_passes", [])
    if len(frozen.pairs) != 1611 or len(passes) != 6444 or len({row["planned_pass_id"] for row in passes}) != 6444:
        raise MultiJudgePreflightError("frozen population/pass identity mismatch")
    per_judge = Counter(row["judge_id"] for row in passes)
    if tuple(sorted(per_judge)) != tuple(sorted(EXPECTED_JUDGES)) or set(per_judge.values()) != {1611}:
        raise MultiJudgePreflightError("frozen per-judge quota mismatch")
    if Counter(row["presentation"] for row in passes) != {"AB": 3222, "BA": 3222}:
        raise MultiJudgePreflightError("frozen presentation quota mismatch")
    if manifest.get("budget_metadata", {}).get("hard_cap_usd") != "2.50":
        raise MultiJudgePreflightError("frozen hard cap mismatch")
    policy = manifest["scientific_configuration"]["retry_policy"]
    if policy.get("retry_policy_version") != RETRY_POLICY_VERSION or policy.get("failure_policy_version") != FAILURE_POLICY_VERSION:
        raise MultiJudgePreflightError("frozen retry/failure policy mismatch")
    _validate_routes_and_pricing(frozen)
    for row in passes:
        pair = frozen.pairs.get(row["canonical_pair_id"])
        if pair is None:
            raise MultiJudgePreflightError("planned pass references an unknown pair")
        expected = (row["original_answer_1_id"], row["original_answer_2_id"]) if row["presentation"] == "AB" else (row["original_answer_2_id"], row["original_answer_1_id"])
        if (row["displayed_A_answer_id"], row["displayed_B_answer_id"]) != expected:
            raise MultiJudgePreflightError("frozen displayed-answer mapping mismatch")
    return frozen


def _validate_routes_and_pricing(frozen: FrozenMultiJudgeManifest) -> None:
    routes = routing_config()
    if routes.get("policy", {}).get("allow_fallbacks") is not False or PRICING_CONFIG.get("version") != "pricing-config-v1":
        raise MultiJudgePreflightError("frozen route/pricing configuration mismatch")
    prices = {row["judge"]: row for row in PRICING_CONFIG.get("models", [])}
    expected_routes = {
        "gpt-4o-mini": "OPENAI_DIRECT",
        "anthropic/claude-3-haiku": "amazon-bedrock",
        "deepseek/deepseek-chat": "streamlake",
        "meta-llama/llama-3.3-70b-instruct": "deepinfra/turbo",
    }
    for judge, row in frozen.judges.items():
        spec = MODEL_REGISTRY.get(judge)
        if spec is None or row["provider"] != spec.provider.value or row["requested_model"] != spec.requested_model or row["route"] != expected_routes[judge] or row["fallbacks_allowed"] is not False:
            raise MultiJudgePreflightError("frozen model/provider/route mismatch")
        if judge not in prices or prices[judge]["model"] != spec.requested_model:
            raise MultiJudgePreflightError("frozen pricing entry missing or mismatched")
        if spec.provider is Provider.OPENROUTER and routes["models"].get(judge, {}).get("upstream_provider") != row["route"]:
            raise MultiJudgePreflightError("active OpenRouter route differs from the manifest")


class MultiJudgeExecutionStore:
    """Dedicated additive PostgreSQL ledger; no legacy evidence table is used."""

    def materialize(self, session: Session, frozen: FrozenMultiJudgeManifest) -> MultiJudgeExecutionBatch:
        batch = session.scalar(select(MultiJudgeExecutionBatch).where(MultiJudgeExecutionBatch.manifest_sha256 == frozen.manifest_sha256))
        if batch is None:
            batch = MultiJudgeExecutionBatch(
                protocol_id=frozen.protocol["protocol_id"], protocol_sha256=frozen.protocol_sha256,
                manifest_id=frozen.manifest["manifest_id"], manifest_sha256=frozen.manifest_sha256,
                hard_cap_usd=HARD_CAP_USD, status="MATERIALIZED",
                provenance_json={"routing_policy_version": routing_policy_version(), "routing_fingerprint": routing_fingerprint(), "pricing_version": PRICING_CONFIG["version"], "created_provider_calls": 0},
            )
            session.add(batch); session.flush()
        elif batch.protocol_sha256 != frozen.protocol_sha256 or batch.hard_cap_usd != HARD_CAP_USD:
            raise MultiJudgePreflightError("existing execution batch does not match the frozen manifest")
        existing = set(session.scalars(select(MultiJudgeExecutionSlot.planned_pass_id).where(MultiJudgeExecutionSlot.batch_id == batch.id)))
        additions = []
        for row in frozen.manifest["planned_passes"]:
            if row["planned_pass_id"] in existing:
                continue
            judge = frozen.judges[row["judge_id"]]
            additions.append(MultiJudgeExecutionSlot(
                batch_id=batch.id, canonical_pair_id=row["canonical_pair_id"], planned_pass_id=row["planned_pass_id"], idempotency_key=row["idempotency_key"],
                judge_id=row["judge_id"], provider=judge["provider"], requested_model=judge["requested_model"], route=judge["route"], presentation=row["presentation"],
                original_answer_1_id=row["original_answer_1_id"], original_answer_2_id=row["original_answer_2_id"], displayed_a_answer_id=row["displayed_A_answer_id"], displayed_b_answer_id=row["displayed_B_answer_id"],
            ))
        if additions:
            session.add_all(additions); session.flush()
        self.validate_materialization(session, batch, frozen)
        return batch

    @staticmethod
    def batch_for_manifest(session: Session, manifest_sha256: str) -> MultiJudgeExecutionBatch:
        batch = session.scalar(select(MultiJudgeExecutionBatch).where(MultiJudgeExecutionBatch.manifest_sha256 == manifest_sha256))
        if batch is None:
            raise MultiJudgePreflightError("frozen execution manifest has not been materialized")
        return batch

    def validate_materialization(self, session: Session, batch: MultiJudgeExecutionBatch, frozen: FrozenMultiJudgeManifest) -> None:
        slots = list(session.scalars(select(MultiJudgeExecutionSlot).where(MultiJudgeExecutionSlot.batch_id == batch.id)))
        if len(slots) != 6444 or len({row.planned_pass_id for row in slots}) != 6444 or len({row.idempotency_key for row in slots}) != 6444:
            raise MultiJudgePreflightError("durable slot uniqueness/count validation failed")
        if Counter(row.judge_id for row in slots) != Counter({judge: 1611 for judge in EXPECTED_JUDGES}) or Counter(row.presentation for row in slots) != {"AB": 3222, "BA": 3222}:
            raise MultiJudgePreflightError("durable slot quota validation failed")
        pair_judges = Counter((row.canonical_pair_id, row.judge_id) for row in slots)
        pair_counts = Counter(row.canonical_pair_id for row in slots)
        if max(pair_judges.values()) != 1 or set(pair_counts.values()) != {4}:
            raise MultiJudgePreflightError("durable pair/judge uniqueness validation failed")
        for row in slots:
            expected = (row.original_answer_1_id, row.original_answer_2_id) if row.presentation == "AB" else (row.original_answer_2_id, row.original_answer_1_id)
            if (row.displayed_a_answer_id, row.displayed_b_answer_id) != expected:
                raise MultiJudgePreflightError("durable displayed-answer mapping mismatch")

    def recover_stale_after_restart(self, session: Session, batch: MultiJudgeExecutionBatch) -> None:
        """Reconcile only expired/no-owner in-flight slots during --execute.

        Read-only status/preflight never calls this method.  A live executor
        owns a SENT slot through its short lease, so an observer cannot turn a
        request that is still in flight into an ambiguous scientific slot.
        """
        now = datetime.utcnow()
        for slot in session.scalars(select(MultiJudgeExecutionSlot).where(MultiJudgeExecutionSlot.batch_id == batch.id, MultiJudgeExecutionSlot.status.in_(("PREPARED", "SENT", "RUNNING")))):
            if slot.status in {"SENT", "RUNNING"} and slot.execution_owner and slot.lease_expires_at and slot.lease_expires_at > now:
                continue
            attempts = list(session.scalars(select(MultiJudgeExecutionAttempt).where(MultiJudgeExecutionAttempt.slot_id == slot.id).order_by(MultiJudgeExecutionAttempt.attempt_index.desc())))
            attempt = attempts[0] if attempts else None
            if slot.status == "PREPARED":
                slot.status = "PENDING"
                if attempt is not None: attempt.state, attempt.completed_at = "ABORTED_BEFORE_TRANSPORT", now
            else:
                slot.status, slot.final_outcome, slot.completed_at = "AMBIGUOUS", "AMBIGUOUS", now
                if attempt is not None: attempt.state, attempt.failure_category, attempt.completed_at = "AMBIGUOUS", "AMBIGUOUS", now
            slot.execution_owner, slot.lease_expires_at, slot.updated_at = None, None, now
        session.flush()

    def reserve_and_mark_sent(self, session: Session, batch: MultiJudgeExecutionBatch, slot_id: Any, forecast_usd: Decimal, *, execution_owner: str, mark_sent: bool = True) -> MultiJudgeExecutionAttempt | None:
        batch = session.scalar(select(MultiJudgeExecutionBatch).where(MultiJudgeExecutionBatch.id == batch.id).with_for_update())
        slot = session.scalar(select(MultiJudgeExecutionSlot).where(MultiJudgeExecutionSlot.id == slot_id).with_for_update())
        if batch is None or slot is None or slot.status != "PENDING":
            return None
        reserved = session.scalar(select(func.coalesce(func.sum(MultiJudgeExecutionAttempt.reserved_usd), Decimal("0"))).join(MultiJudgeExecutionSlot).where(MultiJudgeExecutionSlot.batch_id == batch.id))
        now = datetime.utcnow()
        if Decimal(reserved) + forecast_usd > HARD_CAP_USD:
            attempt = MultiJudgeExecutionAttempt(slot_id=slot.id, attempt_id=hashlib.sha256(f"{slot.planned_pass_id}|budget|{slot.attempt_count}".encode()).hexdigest(), attempt_index=slot.attempt_count, state="BLOCKED_BUDGET", failure_category="BUDGET_EXCEEDED", retry_decision="TERMINAL", reserved_usd=Decimal("0"), completed_at=now, details_json={"forecast_usd": str(forecast_usd), "hard_cap_usd": str(HARD_CAP_USD), "blocked_before_transport": True})
            slot.attempt_count += 1; slot.status = "BUDGET_STOPPED"; slot.final_outcome = "MISSING_PASS"; slot.completed_at = now; slot.execution_owner = None; slot.lease_expires_at = None; slot.updated_at = now
            batch.status, batch.updated_at = "BUDGET_STOPPED", now
            session.add(attempt); session.flush()
            return None
        index = slot.attempt_count
        attempt = MultiJudgeExecutionAttempt(slot_id=slot.id, attempt_id=hashlib.sha256(f"{slot.planned_pass_id}|attempt|{index}".encode()).hexdigest(), attempt_index=index, state="SENT" if mark_sent else "PREPARED", reserved_usd=forecast_usd, details_json={"forecast_usd": str(forecast_usd), "cost_kind": "RESERVED_PRE_REQUEST"})
        slot.attempt_count += 1; slot.status = "SENT" if mark_sent else "PREPARED"; slot.execution_owner = execution_owner if mark_sent else None; slot.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS) if mark_sent else None; slot.started_at = slot.started_at or now; slot.updated_at = now
        batch.status, batch.updated_at = "RUNNING", now
        session.add(attempt); session.flush()
        return attempt

    def persist_result(self, session: Session, slot_id: Any, attempt_id: str, result: NormalizedEvaluationResult, *, execution_owner: str) -> str:
        slot = session.scalar(select(MultiJudgeExecutionSlot).where(MultiJudgeExecutionSlot.id == slot_id).with_for_update())
        attempt = session.scalar(select(MultiJudgeExecutionAttempt).where(MultiJudgeExecutionAttempt.attempt_id == attempt_id).with_for_update())
        if slot is None or attempt is None or slot.status != "SENT" or slot.execution_owner != execution_owner:
            raise MultiJudgePreflightError("result persistence does not match a sent durable slot")
        now = datetime.utcnow()
        actual = _actual_cost(slot.judge_id, result)
        attempt.input_tokens, attempt.output_tokens = result.input_tokens, result.output_tokens
        attempt.actual_usd, attempt.provider_response_id, attempt.effective_model = actual, result.provider_response_id, result.effective_model
        attempt.route_provenance_json = result.route_provenance
        metadata = {"parse_status": result.parse_status, "provider_response_id": result.provider_response_id, "effective_model": result.effective_model, "model_version": result.model_version, "latency_ms": result.latency_ms, "criteria_scores": result.criterion_scores, "explanation": result.explanation}
        slot.raw_response_metadata = metadata
        category = result.error_code or {Outcome.TIMEOUT: "TIMEOUT", Outcome.API_ERROR: "PROVIDER_ERROR", Outcome.INVALID_RESPONSE: "INVALID_RESPONSE", Outcome.REFUSAL: "REFUSAL"}.get(result.outcome)
        if result.outcome in {Outcome.ANSWER_A, Outcome.ANSWER_B, Outcome.TIE, Outcome.UNKNOWN}:
            slot.status, slot.final_outcome, slot.mapped_vote = "COMPLETED", result.outcome.value, _map_vote(slot, result.outcome)
            attempt.state, attempt.retry_decision = "SUCCEEDED", "FINAL"
            slot.completed_at = now
        else:
            rule = retry_rule(category or "CONFIGURATION")
            if rule.retryable and attempt.attempt_index < rule.max_retries:
                slot.status, attempt.state, attempt.retry_decision = "PENDING", "FAILED_RETRYABLE", "RETRY"
            else:
                slot.status, slot.final_outcome, slot.mapped_vote = "FAILED_FINAL", result.outcome.value, None
                attempt.state, attempt.retry_decision, slot.completed_at = "FAILED_FINAL", "TERMINAL", now
            attempt.failure_category = category
        attempt.completed_at, slot.execution_owner, slot.lease_expires_at, slot.updated_at = now, None, None, now
        session.flush()
        return slot.status

    def status(self, session: Session, batch: MultiJudgeExecutionBatch) -> dict[str, Any]:
        slots = list(session.scalars(select(MultiJudgeExecutionSlot).where(MultiJudgeExecutionSlot.batch_id == batch.id)))
        attempts = list(session.scalars(select(MultiJudgeExecutionAttempt).join(MultiJudgeExecutionSlot).where(MultiJudgeExecutionSlot.batch_id == batch.id)))
        states = Counter(row.status for row in slots)
        reserved = sum((Decimal(row.reserved_usd or 0) for row in attempts), Decimal("0"))
        actual = sum((Decimal(row.actual_usd or 0) for row in attempts), Decimal("0"))
        return {"completed_scientific_slots": states["COMPLETED"], "terminal_failures": states["FAILED_FINAL"] + states["BUDGET_STOPPED"], "ambiguous": states["AMBIGUOUS"], "in_flight": states["SENT"] + states["RUNNING"], "attempts": len(attempts), "retries": sum(row.attempt_index > 0 for row in attempts), "pending": states["PENDING"], "cumulative_reserved_usd": str(reserved), "cumulative_actual_usd": str(actual), "spend_remaining_usd": str(HARD_CAP_USD - reserved), "batch_status": batch.status}


def _actual_cost(judge_id: str, result: NormalizedEvaluationResult) -> Decimal | None:
    if result.provider_reported_cost is not None:
        try: return Decimal(str(result.provider_reported_cost))
        except Exception: pass
    if result.input_tokens is not None and result.output_tokens is not None:
        rate = price_for_model(judge_id)
        return Decimal(result.input_tokens) * rate.input_per_token + Decimal(result.output_tokens) * rate.output_per_token
    return None


def _map_vote(slot: MultiJudgeExecutionSlot, outcome: Outcome) -> str | None:
    if outcome is Outcome.TIE: return "TIE"
    # UNKNOWN is a completed, explicitly non-decisive provider outcome.  It
    # must remain a non-vote rather than being forced through answer identity
    # mapping (which only applies to displayed A/B verdicts).
    if outcome is Outcome.UNKNOWN: return None
    answer_id = slot.displayed_a_answer_id if outcome is Outcome.ANSWER_A else slot.displayed_b_answer_id if outcome is Outcome.ANSWER_B else None
    if answer_id == slot.original_answer_1_id: return "ORIGINAL_ANSWER_1"
    if answer_id == slot.original_answer_2_id: return "ORIGINAL_ANSWER_2"
    raise MultiJudgePreflightError("provider outcome cannot map to a frozen original answer")


def format_live_progress(report: dict[str, Any]) -> str:
    """Render only operational, already-durable ledger state."""
    completed = int(report["completed_scientific_slots"])
    terminal = int(report["terminal_failures"])
    resolved = completed + terminal
    percentage = (100 * resolved) / 6444
    return (
        f"[{resolved:5d} / 6444] {percentage:5.2f}% | pending {report['pending']} | "
        f"attempts {report['attempts']} | retries {report['retries']} | "
        f"failed {terminal} | ambiguous {report['ambiguous']} | "
        f"spend reserved ${report['cumulative_reserved_usd']} "
        f"(actual ${report['cumulative_actual_usd']}) / $2.50"
    )


def _report_progress(callback: Callable[[dict[str, Any]], None] | None, report: dict[str, Any]) -> None:
    if callback is None:
        return
    try:
        callback(dict(report))
    except Exception:
        # Reporting is observational and must never alter execution safety.
        pass


class MultiJudgeRealRunner:
    def __init__(self, *, transport: Transport | None = None) -> None:
        self.frozen = load_frozen_manifest()
        self.store = MultiJudgeExecutionStore()
        self.transport = transport

    @staticmethod
    def _payload_source() -> tuple[dict[int, str], dict[int, str]]:
        # Execution reads only frozen prompt/answer source records, never
        # human preference rows, labels, earlier verdicts, or consensus data.
        return ({int(row[0]): str(row[1]) for row in _copy_rows("prompts")}, {int(row[0]): str(row[3]) for row in _copy_rows("answers")})

    def preflight(self, session: Session) -> dict[str, Any]:
        """Read-only status/preflight safe to invoke during a paid run."""
        batch = self.store.batch_for_manifest(session, self.frozen.manifest_sha256)
        self.store.validate_materialization(session, batch, self.frozen)
        status = self.store.status(session, batch)
        credentials = credential_presence()
        # An AMBIGUOUS slot is deliberately retained and skipped, not replayed.
        # Its presence must not prevent safely resuming the other pending slots.
        ready = all(credentials.values()) and status["batch_status"] != "BUDGET_STOPPED" and status["completed_scientific_slots"] + status["terminal_failures"] + status["ambiguous"] + status["in_flight"] + status["pending"] == 6444
        return {"state": "READY" if ready else "NOT READY", "credentials": {key: "PRESENT" if value else "MISSING" for key, value in credentials.items()}, "protocol_sha256": self.frozen.protocol_sha256, "manifest_sha256": self.frozen.manifest_sha256, "materialized_pairs": 1611, "materialized_planned_passes": 6444, "hard_cap_usd": str(HARD_CAP_USD), "routing_policy_version": routing_policy_version(), "retry_policy": RETRY_POLICY_VERSION, "failure_policy": FAILURE_POLICY_VERSION, **status}

    def _prepare_execution(self, session: Session) -> dict[str, Any]:
        """The only writing reconciliation path; callable only by --execute."""
        batch = self.store.materialize(session, self.frozen)
        self.store.recover_stale_after_restart(session, batch)
        return self.preflight(session)

    def execute(self, session_factory: Callable[[], Session], *, confirm_paid_run: str, max_slots: int | None = None, progress_callback: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
        if confirm_paid_run != PAID_CONFIRMATION:
            raise MultiJudgePreflightError("paid execution requires the exact explicit confirmation")
        if not all(credential_presence().values()):
            raise MultiJudgePreflightError("required provider credentials are missing")
        execution_owner = uuid4().hex
        with session_factory() as session:
            preflight = self._prepare_execution(session); session.commit()
            if preflight["state"] != "READY":
                raise MultiJudgePreflightError("paid execution preflight is not ready")
        _report_progress(progress_callback, preflight)
        source_prompts, source_answers = self._payload_source()
        processed, last_progress = 0, monotonic()
        while max_slots is None or processed < max_slots:
            with session_factory() as session:
                batch = self.store.batch_for_manifest(session, self.frozen.manifest_sha256)
                slot = session.scalar(select(MultiJudgeExecutionSlot).where(MultiJudgeExecutionSlot.batch_id == batch.id, MultiJudgeExecutionSlot.status == "PENDING").order_by(MultiJudgeExecutionSlot.planned_pass_id))
                if slot is None:
                    report = self.store.status(session, batch); session.commit(); return report
                prompt_id = self.frozen.pairs[slot.canonical_pair_id]["prompt_id"]
                question, answer_a, answer_b = source_prompts[prompt_id], source_answers[slot.displayed_a_answer_id], source_answers[slot.displayed_b_answer_id]
                forecast = _forecast_usd(slot.judge_id, question, answer_a, answer_b)
                attempt = self.store.reserve_and_mark_sent(session, batch, slot.id, forecast, execution_owner=execution_owner)
                session.commit()
                if attempt is None:
                    return self.store.status(session, batch)
                slot_id, attempt_id, judge_id = slot.id, attempt.attempt_id, slot.judge_id
                original_a, original_b = slot.original_answer_1_id, slot.original_answer_2_id
                displayed_a, displayed_b = slot.displayed_a_answer_id, slot.displayed_b_answer_id
            result = self._evaluate(slot_id, judge_id, question, answer_a, answer_b, original_a, original_b, displayed_a, displayed_b)
            with session_factory() as session:
                state = self.store.persist_result(session, slot_id, attempt_id, result, execution_owner=execution_owner)
                batch = self.store.batch_for_manifest(session, self.frozen.manifest_sha256)
                report = self.store.status(session, batch); session.commit()
            processed += 1
            if processed % 10 == 0 or monotonic() - last_progress >= 5:
                _report_progress(progress_callback, report); last_progress = monotonic()
            if state == "BUDGET_STOPPED":
                return report
        _report_progress(progress_callback, report)
        return report

    def _evaluate(self, slot_id: Any, judge_id: str, question: str, answer_a: str, answer_b: str, original_a: int, original_b: int, displayed_a: int, displayed_b: int) -> NormalizedEvaluationResult:
        spec = MODEL_REGISTRY[judge_id]
        request = EvaluationRequest(question=question, answer_a=answer_a, answer_b=answer_b, judge_name=judge_id, provider=spec.provider, requested_model=spec.requested_model, temperature=0.0, top_p=1.0, seed=None, prompt_template_version="controlled-judge-pairwise-v1", experiment_id=slot_id, controlled_unit_id=slot_id, repetition_index=0, pass_number=1, original_answer_a_id=original_a, original_answer_b_id=original_b, presented_answer_a_id=displayed_a, presented_answer_b_id=displayed_b)
        gate = ProviderExecutionGate(mode="REAL", authorization_token="explicit-paid-run", verified_pricing_version=PRICING_CONFIG["version"], max_provider_calls=6444, max_input_tokens=10**9, max_output_tokens=6444 * 350, max_usd=float(HARD_CAP_USD))
        adapter = adapter_for_judge(judge_id, transport=self.transport or environment_http_transport, gate=gate)
        return ControlledEvaluationEngine(adapter).evaluate(request)


def _forecast_usd(judge_id: str, question: str, answer_a: str, answer_b: str) -> Decimal:
    tokens = (len(question) + len(answer_a) + len(answer_b) + 600 + 3) // 4
    rate = price_for_model(judge_id)
    return Decimal(tokens) * rate.input_per_token + Decimal(MODEL_REGISTRY[judge_id].max_output_tokens) * rate.output_per_token
