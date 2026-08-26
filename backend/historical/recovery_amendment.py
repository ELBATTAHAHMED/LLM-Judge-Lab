"""Build the additive, provider-free source-corrected recovery amendment.

This builder never claims a slot, changes the execution ledger, or contacts a
provider.  It turns the terminal FAILED/AMBIGUOUS logical slots from the
original corrected batch into a separately identified recovery manifest.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_UP
from pathlib import Path
from typing import Any

from sqlalchemy import select

from backend.core.database import SessionLocal
from backend.historical.source_corrected_plan import MANIFEST_PATH, stable_sha
from backend.historical.source_corrected_models import (SourceCorrectedExecutionAttempt,
                                               SourceCorrectedExecutionBatch,
                                               SourceCorrectedExecutionSlot)


ROOT = Path(__file__).resolve().parent.parent.parent
RECOVERY_MANIFEST_PATH = ROOT / "evidence" / "remediation" / "source_corrected_recovery_manifest_v1.json"
AMENDMENT_PATH = ROOT / "evidence" / "remediation" / "source_corrected_recovery_amendment_v1.json"
AMENDMENT_IDENTITY = "source-corrected-recovery-amendment-v1"
RECOVERY_MANIFEST_IDENTITY = "source-corrected-recovery-manifest-v1"
TERMINAL_REPLACEMENT_STATES = frozenset({"FAILED", "AMBIGUOUS"})


def _canonical_sha(value: dict[str, Any]) -> str:
    return stable_sha(value)


def _load_parent_manifest() -> dict[str, Any]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if payload.get("manifest_identity") != "controlled-source-text-corrected-execution-manifest-v1":
        raise RuntimeError("unexpected corrected parent manifest identity")
    return payload


def _cost_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_provider: dict[str, list[Decimal]] = defaultdict(list)
    for row in rows:
        by_provider[row["provider"]].append(Decimal(row["estimated_usd"]))
    expected = {provider: sum(costs, Decimal("0")) for provider, costs in by_provider.items()}
    p90 = {
        provider: sorted(costs)[math.ceil(0.90 * len(costs)) - 1] * len(costs)
        for provider, costs in by_provider.items()
    }
    p90_plus_15 = {
        provider: (amount * Decimal("1.15")).quantize(Decimal("0.00000001"), rounding=ROUND_UP)
        for provider, amount in p90.items()
    }
    # Recovery permits at most the initial recovery send plus two bounded
    # retries for transient categories.  This is a hard spending envelope,
    # not an expected expenditure.
    retry_envelope = {
        provider: (amount * 3).quantize(Decimal("0.00000001"), rounding=ROUND_UP)
        for provider, amount in expected.items()
    }
    return {
        "pricing_basis": "original frozen per-slot estimates; no provider query",
        "expected_usd": {key: str(value) for key, value in sorted(expected.items())},
        "expected_total_usd": str(sum(expected.values(), Decimal("0"))),
        "p90_method": "per-provider 90th-percentile frozen slot estimate multiplied by recovery-slot count",
        "p90_usd": {key: str(value) for key, value in sorted(p90.items())},
        "p90_total_usd": str(sum(p90.values(), Decimal("0"))),
        "p90_plus_15_percent_usd": {key: str(value) for key, value in sorted(p90_plus_15.items())},
        "p90_plus_15_percent_total_usd": str(sum(p90_plus_15.values(), Decimal("0"))),
        "bounded_retry_hard_cap_usd": {key: str(value) for key, value in sorted(retry_envelope.items())},
        "bounded_retry_hard_cap_total_usd": str(sum(retry_envelope.values(), Decimal("0"))),
    }


def build() -> tuple[dict[str, Any], dict[str, Any]]:
    parent = _load_parent_manifest()
    planned = {row["planned_pass_id"]: row for row in parent["planned_passes"]}
    with SessionLocal() as session:
        batch = session.scalar(
            select(SourceCorrectedExecutionBatch).where(
                SourceCorrectedExecutionBatch.manifest_sha256 == parent["manifest_sha256"]
            )
        )
        if batch is None or batch.status != "COMPLETED":
            raise RuntimeError("corrected execution batch is not terminally completed")
        slots = list(session.scalars(
            select(SourceCorrectedExecutionSlot).where(
                SourceCorrectedExecutionSlot.batch_id == batch.id,
                SourceCorrectedExecutionSlot.state.in_(TERMINAL_REPLACEMENT_STATES),
            ).order_by(SourceCorrectedExecutionSlot.planned_pass_id)
        ))
        completed = set(session.scalars(
            select(SourceCorrectedExecutionSlot.planned_pass_id).where(
                SourceCorrectedExecutionSlot.batch_id == batch.id,
                SourceCorrectedExecutionSlot.state == "COMPLETED",
            )
        ))
        attempts_by_slot: dict[Any, list[SourceCorrectedExecutionAttempt]] = defaultdict(list)
        for attempt in session.scalars(select(SourceCorrectedExecutionAttempt).join(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == batch.id)):
            attempts_by_slot[attempt.slot_id].append(attempt)

        recovery_slots: list[dict[str, Any]] = []
        for slot in slots:
            parent_row = planned.get(slot.planned_pass_id)
            if parent_row is None:
                raise RuntimeError("terminal corrected slot is absent from frozen parent manifest")
            if slot.planned_pass_id in completed:
                raise RuntimeError("recovery manifest intersects completed corrected work")
            attempts = sorted(attempts_by_slot[slot.id], key=lambda value: value.attempt_index)
            reason = (
                "OPERATIONAL_REPLACEMENT_FOR_AMBIGUOUS"
                if slot.state == "AMBIGUOUS"
                else f"OPERATIONAL_REPLACEMENT_FOR_FAILED_{slot.error_category}"
            )
            recovery_slots.append({
                "recovery_slot_id": stable_sha({"amendment": AMENDMENT_IDENTITY, "original_slot_id": str(slot.id)}),
                "recovery_idempotency_key": stable_sha({"amendment": AMENDMENT_IDENTITY, "original_planned_pass_id": slot.planned_pass_id, "payload_sha256": slot.payload_sha256}),
                "original_logical_slot_id": str(slot.id),
                "original_planned_pass_id": slot.planned_pass_id,
                "original_idempotency_key": slot.idempotency_key,
                "historical_terminal_state": slot.state,
                "historical_final_outcome": slot.final_outcome,
                "historical_failure_category": slot.error_category,
                "historical_attempt_lineage": [
                    {
                        "attempt_id": item.attempt_id,
                        "attempt_index": item.attempt_index,
                        "state": item.state,
                        "failure_category": item.failure_category,
                        "retry_decision": item.retry_decision,
                        "provider_response_id_present": item.provider_response_id is not None,
                    }
                    for item in attempts
                ],
                "recovery_reason": reason,
                "replacement_counting_rule": "ONE_VALID_RECOVERY_RESULT_FOR_THE_ORIGINAL_LOGICAL_SLOT; historical failed/ambiguous attempts remain excluded",
                "corrected_dataset_version": parent_row["corrected_dataset_version"],
                "corrected_record_key": parent_row["corrected_record_key"],
                "rendered_payload_sha256": parent_row["rendered_payload_sha256"],
                "source_corrected_payload": parent_row["source_corrected_payload"],
                "prompt_id": parent_row["prompt_id"],
                "prompt_sha256": parent_row["prompt_sha256"],
                "prompt_template_version": parent_row["prompt_template_version"],
                "prompt_template_sha256": parent_row["prompt_template_sha256"],
                "judge_id": parent_row["judge_id"],
                "provider": parent_row["provider"],
                "provider_model": parent_row.get("provider_model"),
                "route": parent_row["route"],
                "routing_policy_version": parent_row["routing_policy_version"],
                "routing_fingerprint": parent_row["routing_fingerprint"],
                "temperature": parent_row.get("temperature"),
                "top_p": parent_row.get("top_p"),
                "seed": parent_row.get("seed"),
                "rq_code": parent_row["rq_code"],
                "condition_code": parent_row["condition_code"],
                "presentation": parent_row["presentation"],
                "repetition_index": parent_row.get("repetition_index"),
                "transform": parent_row.get("transform"),
                "estimated_input_tokens": parent_row["estimated_input_tokens"],
                "estimated_output_tokens": parent_row["estimated_output_tokens"],
                "estimated_usd": parent_row["estimated_usd"],
            })

        terminal_counts = Counter(slot.state for slot in slots)
        historical_actual = sum((Decimal(slot.actual_usd or 0) for slot in session.scalars(select(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == batch.id))), Decimal("0"))
        historical_reserved = sum((Decimal(attempt.reserved_usd or 0) for attempt in session.scalars(select(SourceCorrectedExecutionAttempt).join(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == batch.id, SourceCorrectedExecutionAttempt.actual_usd.is_(None)))), Decimal("0"))
        terminal_time = max(
            value for value in [slot.completed_at for slot in slots] if value is not None
        ).isoformat()

    recovery_slots.sort(key=lambda row: row["original_planned_pass_id"])
    costs = _cost_summary(recovery_slots)
    per_rq = Counter(row["rq_code"] for row in recovery_slots)
    per_judge = Counter(row["judge_id"] for row in recovery_slots)
    recovery_manifest = {
        "recovery_manifest_identity": RECOVERY_MANIFEST_IDENTITY,
        "schema_version": 1,
        "generated_from_terminal_execution_at": terminal_time,
        "provider_calls": 0,
        "parent_corrected_manifest": {
            "identity": parent["manifest_identity"],
            "sha256": parent["manifest_sha256"],
            "path": str(MANIFEST_PATH.relative_to(ROOT)).replace("\\", "/"),
        },
        "eligibility_rule": "exactly terminal FAILED or AMBIGUOUS slots from the parent batch; completed parent slots are forbidden",
        "counts": {
            "failed_replacements": terminal_counts["FAILED"],
            "ambiguous_replacements": terminal_counts["AMBIGUOUS"],
            "total_recovery_slots": len(recovery_slots),
            "per_rq": dict(sorted(per_rq.items())),
            "per_judge": dict(sorted(per_judge.items())),
            "completed_slot_overlap": len({row["original_planned_pass_id"] for row in recovery_slots} & completed),
        },
        "budget": costs,
        "recovery_slots": recovery_slots,
    }
    recovery_manifest["recovery_manifest_sha256"] = _canonical_sha(recovery_manifest)

    global_cap = Decimal(str(parent["budget_metadata"]["global_hard_cap_usd"]))
    remaining_headroom = global_cap - historical_actual - historical_reserved
    amendment = {
        "amendment_identity": AMENDMENT_IDENTITY,
        "schema_version": 1,
        "generated_from_terminal_execution_at": terminal_time,
        "provider_calls": 0,
        "original_protocol_unchanged": True,
        "operational_not_estimand_amendment": True,
        "parent_corrected_manifest": recovery_manifest["parent_corrected_manifest"],
        "terminal_execution": {
            "batch_status": "COMPLETED",
            "completed": 6330,
            "failed": terminal_counts["FAILED"],
            "ambiguous": terminal_counts["AMBIGUOUS"],
            "historical_actual_usd": str(historical_actual),
            "historical_held_reserved_usd": str(historical_reserved),
        },
        "recovery_manifest": {
            "identity": RECOVERY_MANIFEST_IDENTITY,
            "path": str(RECOVERY_MANIFEST_PATH.relative_to(ROOT)).replace("\\", "/"),
            "sha256": recovery_manifest["recovery_manifest_sha256"],
        },
        "eligibility": {
            "completed_slots_replayed": False,
            "completed_slot_overlap": recovery_manifest["counts"]["completed_slot_overlap"],
            "failed_slots_receive_fresh_recovery_identity": True,
            "ambiguous_slot_policy": "ONE_NEW_OPERATIONAL_REPLACEMENT_FOR_AMBIGUOUS; original send remains non-replayable and its receipt remains unknown",
            "required_frozen_identity_fields": [
                "corrected_dataset_version", "corrected_record_key", "rendered_payload_sha256", "source_corrected_payload",
                "prompt_id", "prompt_sha256", "prompt_template_version", "prompt_template_sha256",
                "judge_id", "provider", "provider_model", "route", "routing_policy_version", "routing_fingerprint",
                "temperature", "top_p", "seed", "rq_code", "condition_code", "presentation", "repetition_index", "transform",
            ],
        },
        "operational_retry_policy": {
            "identity": "source-corrected-recovery-retry-v1",
            "recovery_attempts_are_not_historical_retries": True,
            "global_concurrency": 1,
            "provider_concurrency": {"OPENAI": 1, "OPENROUTER": 1},
            "minimum_seconds_between_new_requests": {"OPENAI": 5, "OPENROUTER": 10, "deepseek/deepseek-chat": 30},
            "retryable_categories": ["RATE_LIMIT", "TEMPORARY_5XX", "NETWORK_CONNECTION", "CONNECTION", "TIMEOUT", "INVALID_RESPONSE"],
            "max_additional_recovery_retries": {"RATE_LIMIT": 2, "TEMPORARY_5XX": 2, "NETWORK_CONNECTION": 2, "CONNECTION": 2, "TIMEOUT": 1, "INVALID_RESPONSE": 1},
            "backoff_seconds": {"RATE_LIMIT": [120, 300], "TEMPORARY_5XX": [60, 180], "NETWORK_CONNECTION": [60, 180], "CONNECTION": [60, 180], "TIMEOUT": [60], "INVALID_RESPONSE": [30]},
            "invalid_response_policy": "a malformed historical response is never repaired; one new recovery call with identical scientific input may supply the missing usable observation",
            "stop_conditions": ["recovery hard-cap reached", "frozen payload/model/route invariant failure", "database persistence integrity failure", "provider credential/configuration failure"],
        },
        "scientific_interpretation": {
            "estimands_changed": False,
            "rq1": "independent missing observations may be replaced without changing the alignment estimand",
            "rq2": "one fresh valid draw replaces each operationally lost planned repetition; no historical ambiguous/failed output is counted",
            "rq3": "replacement restores the originally planned AB/BA pair",
            "rq4": "replacement restores the originally planned original/transformed pair",
            "rq5": "no recovery; already complete",
            "rq6": "no recovery; already complete",
            "rq7_primary": "replacement restores the planned baseline plus DUAL_SWAP matched triplet",
            "rq7_secondary": "replacement restores the missing member of a strict four-judge vote set",
        },
        "budget": {
            **costs,
            "remaining_original_global_headroom_usd": str(remaining_headroom),
            "recovery_hard_cap_within_remaining_headroom": Decimal(costs["bounded_retry_hard_cap_total_usd"]) <= remaining_headroom,
            "projected_cumulative_actual_plus_expected_recovery_usd": str(historical_actual + Decimal(costs["expected_total_usd"])),
        },
        "execution_plan": {
            "architecture": "extend the existing resumable source-corrected executor with a separate recovery batch/slot namespace; do not mutate the parent batch",
            "execution_status": "NOT_IMPLEMENTED_BY_DESIGN_ONLY_AMENDMENT",
            "provider_execution_authorized": False,
            "paid_command": None,
            "command_blocker": "an additive recovery executor must be implemented and separately preflighted against this manifest before a safe paid command exists",
        },
        "historical_evidence_unchanged": ["phase11", "research_release_v2", "research_release_v3", "multijudge_consensus"],
    }
    amendment["amendment_sha256"] = _canonical_sha(amendment)
    return recovery_manifest, amendment


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    recovery_manifest, amendment = build()
    if args.verify:
        if not RECOVERY_MANIFEST_PATH.exists() or not AMENDMENT_PATH.exists():
            raise SystemExit("recovery amendment artifacts are missing")
        stored_manifest = json.loads(RECOVERY_MANIFEST_PATH.read_text(encoding="utf-8"))
        stored_amendment = json.loads(AMENDMENT_PATH.read_text(encoding="utf-8"))
        if stored_manifest != recovery_manifest or stored_amendment != amendment:
            raise SystemExit("recovery amendment artifacts do not deterministically match the terminal ledger")
        print("SOURCE_CORRECTED_RECOVERY_AMENDMENT_VERIFIED")
        return 0
    _write(RECOVERY_MANIFEST_PATH, recovery_manifest)
    _write(AMENDMENT_PATH, amendment)
    print(json.dumps({"recovery_manifest_sha256": recovery_manifest["recovery_manifest_sha256"], "amendment_sha256": amendment["amendment_sha256"], "recovery_slots": recovery_manifest["counts"]["total_recovery_slots"], "provider_calls": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
