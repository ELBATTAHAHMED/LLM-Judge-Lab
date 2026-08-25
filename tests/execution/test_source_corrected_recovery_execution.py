"""Provider-free integration checks for the additive 119-slot recovery worker."""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from controlled_models import DatasetVersion
from database import SessionLocal
from models import Prompt
from source_corrected_execution_models import (SourceCorrectedExecutionAttempt,
                                               SourceCorrectedExecutionBatch,
                                               SourceCorrectedExecutionSlot)
from source_corrected_real_execution import MockTransport, SourceCorrectedStore, utc_now
from source_corrected_recovery_execution import (AMENDMENT_SHA, CONFIRMATION, RECOVERY_MANIFEST_SHA,
                                                 RecoveryPayloadResolver, SourceCorrectedRecoveryRunner,
                                                 _read_verified_artifacts, recovery_backoff_seconds,
                                                 recovery_retry_rule, render_recovery_dashboard)


def _isolated_recovery_runner():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    for table in (DatasetVersion.__table__, Prompt.__table__, SourceCorrectedExecutionBatch.__table__,
                  SourceCorrectedExecutionSlot.__table__, SourceCorrectedExecutionAttempt.__table__):
        table.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    manifest, _ = _read_verified_artifacts()
    manifest = deepcopy(manifest)
    sleeps: list[float] = []
    with SessionLocal() as source:
        prompt_ids = {row["prompt_id"] for row in manifest["recovery_slots"]}
        prompts = list(source.scalars(select(Prompt).where(Prompt.id.in_(prompt_ids))))
    with factory() as session:
        version = DatasetVersion(id=uuid4(), source_name="isolated", version="source-text-corrected-v1",
                                 source_checksum="0" * 64, import_status="SUCCEEDED")
        parent = SourceCorrectedExecutionBatch(
            id=uuid4(), dataset_version_id=version.id, reconciliation_sha256="0" * 64,
            manifest_identity=manifest["parent_corrected_manifest"]["identity"],
            manifest_sha256=manifest["parent_corrected_manifest"]["sha256"], global_hard_cap_usd=Decimal("10"),
            provider_hard_caps_json={"OPENAI": "10", "OPENROUTER": "10"}, status="COMPLETED", provenance_json={})
        session.add_all((version, parent)); session.add_all(Prompt(id=p.id, text=p.text, category=p.category) for p in prompts)
        for index, row in enumerate(manifest["recovery_slots"]):
            parent_id = uuid4()
            row["original_logical_slot_id"] = str(parent_id)
            session.add(SourceCorrectedExecutionSlot(
                id=parent_id, batch_id=parent.id, planned_pass_id=row["original_planned_pass_id"],
                idempotency_key=row["original_idempotency_key"], rq_code=row["rq_code"], judge_id=row["judge_id"],
                provider=row["provider"], route=row["route"], payload_sha256=row["rendered_payload_sha256"],
                state=row["historical_terminal_state"], estimated_input_tokens=row["estimated_input_tokens"],
                estimated_output_tokens=row["estimated_output_tokens"], final_outcome="AMBIGUOUS" if index == 0 else "MISSING_PASS"))
        session.commit()
    runner = SourceCorrectedRecoveryRunner(factory, transport=MockTransport(), sleep_fn=sleeps.append)
    runner.manifest = manifest
    runner.resolver = RecoveryPayloadResolver(manifest)
    return engine, factory, runner, sleeps


def test_frozen_artifacts_and_recovery_policy_are_exact():
    manifest, amendment = _read_verified_artifacts()
    assert manifest["recovery_manifest_sha256"] == RECOVERY_MANIFEST_SHA
    assert amendment["amendment_sha256"] == AMENDMENT_SHA
    assert len(manifest["recovery_slots"]) == 119
    assert manifest["counts"]["completed_slot_overlap"] == 0
    assert recovery_retry_rule("INVALID_RESPONSE").max_retries == 1
    assert recovery_backoff_seconds("RATE_LIMIT", 0) == 120
    assert recovery_backoff_seconds("RATE_LIMIT", 1) == 300


def test_additive_materialization_preserves_parent_and_uses_new_idempotency():
    engine, factory, runner, _sleeps = _isolated_recovery_runner()
    ready = runner.preflight()
    assert ready["status"] == "READY" and ready["slots"] == 119 and ready["overlap"] == 0
    with factory() as session:
        parent = session.scalar(select(SourceCorrectedExecutionBatch).where(SourceCorrectedExecutionBatch.status == "COMPLETED"))
        recovery = runner.batch(session)
        original = list(session.scalars(select(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == parent.id)))
        replacements = list(session.scalars(select(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == recovery.id)))
    assert len(original) == len(replacements) == 119
    assert all(slot.state in {"FAILED", "AMBIGUOUS"} for slot in original)
    assert {slot.original_logical_slot_id for slot in replacements} == {slot.id for slot in original}
    assert not ({slot.idempotency_key for slot in original} & {slot.idempotency_key for slot in replacements})
    assert all(slot.recovery_lineage_json and slot.recovery_lineage_json["corrected_source_answer_hashes"] for slot in replacements)
    assert all(slot.recovery_lineage_json["historical_attempt_lineage"] for slot in replacements)
    engine.dispose()


def test_full_mock_recovery_uses_same_execution_path_and_resumes_without_duplicates():
    engine, factory, runner, sleeps = _isolated_recovery_runner()
    runner.preflight()
    partial = runner.execute(confirmation=CONFIRMATION, max_slots=5)
    final = runner.execute_mock_full()
    assert partial["completed"] == 5
    assert final["planned"] == final["completed"] == final["attempts"] == 119
    assert final["failed"] == final["ambiguous"] == 0
    assert any(delay > 0 for delay in sleeps)  # DeepSeek's serial 30-second gate was invoked.
    dashboard = render_recovery_dashboard(final, {"OPENAI": "1", "OPENROUTER": "2", "GLOBAL": "3"})
    assert "SOURCE-CORRECTED RECOVERY" in dashboard and "119 / 119" in dashboard
    assert "Expected $0.0522640002" in dashboard and "Recovery headroom" in dashboard
    engine.dispose()


def test_crash_after_send_is_ambiguous_and_never_auto_replayed():
    engine, factory, runner, _sleeps = _isolated_recovery_runner()
    runner.preflight()
    with factory() as session:
        batch = runner.batch(session)
        slot = session.scalar(select(SourceCorrectedExecutionSlot).where(SourceCorrectedExecutionSlot.batch_id == batch.id))
        session.add(SourceCorrectedExecutionAttempt(slot_id=slot.id, attempt_id="crash-sent", attempt_index=0, state="SENT", reserved_usd=Decimal("0.0001")))
        slot.state, slot.attempt_count, slot.execution_owner, slot.lease_expires_at = "SENT", 1, "dead", utc_now() - timedelta(seconds=1)
        session.commit()
    report = runner.reconcile_stale_in_flight()
    with factory() as session:
        batch = runner.batch(session)
        slot = session.scalar(select(SourceCorrectedExecutionSlot).where(
            SourceCorrectedExecutionSlot.batch_id == batch.id,
            SourceCorrectedExecutionSlot.state == "AMBIGUOUS"))
        attempts = list(session.scalars(select(SourceCorrectedExecutionAttempt).where(SourceCorrectedExecutionAttempt.slot_id == slot.id)))
    assert report["ambiguous"] == 1 and len(attempts) == 1 and attempts[0].retry_decision == "TERMINAL"
    engine.dispose()


def test_invalid_response_retry_is_one_fresh_recovery_attempt_and_paid_gate_is_exact():
    engine, factory, runner, _sleeps = _isolated_recovery_runner()
    with pytest.raises(Exception, match="exact confirmation"):
        runner.execute(confirmation="not-the-confirmation", max_slots=1)
    runner.preflight()
    store = SourceCorrectedStore()
    with factory() as session:
        batch = runner.batch(session)
        slot, attempt = store.claim(session, batch, owner="test")
        store.mark_sent(session, slot.id, attempt.attempt_id, owner="test")
        from controlled_evaluation import NormalizedEvaluationResult
        from controlled_persistence import Outcome
        invalid = NormalizedEvaluationResult(Outcome.INVALID_RESPONSE, None, None, None, None, "mock", None, None,
                                             "mock", 0, "INVALID", "INVALID_RESPONSE", "malformed")
        assert store.persist(session, slot.id, attempt.attempt_id, invalid, owner="test",
                             retry_policy=recovery_retry_rule, retry_delay_seconds=30) == "PENDING"
        assert slot.next_eligible_at is not None
        session.commit()
    engine.dispose()
