"""Provider-free regression coverage for the frozen source-correction plan."""
from __future__ import annotations

from collections import Counter
from decimal import Decimal
from uuid import uuid4
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.core.database import SessionLocal
from backend.core.controlled_models import DatasetVersion
from backend.historical.source_corrected_plan import (CONFIRMATION, DATASET_VERSION, RECONCILIATION_SHA256, SourceCorrectedExecutionStore,
                                        SourceCorrectedPreflightError, build_plan, mock_dry_run)
from backend.historical.source_corrected_models import (SourceCorrectedExecutionAttempt, SourceCorrectedExecutionBatch,
                                               SourceCorrectedExecutionSlot)


def test_corrected_plan_consumes_only_the_frozen_498_record_map():
    with SessionLocal() as session:
        manifest, ledger = build_plan(session)
        repeat, _ = build_plan(session)
    assert manifest["manifest_sha256"] == repeat["manifest_sha256"]
    assert manifest["execution_authorized"] is False
    assert manifest["dataset_version"] == DATASET_VERSION
    assert manifest["reconciliation_artifact"] == {
        "identity": "source-text-reconciliation-v1", "sha256": RECONCILIATION_SHA256,
        "affected_record_keys_consumed": 498, "heuristic_rediscovery": False,
    }
    assert manifest["counts"]["total_rerun_passes"] == 6449
    assert manifest["counts"]["per_rq"] == {"RQ1": 229, "RQ2": 2410, "RQ3": 512, "RQ4": 138, "RQ5": 102, "RQ6": 337, "RQ7_PRIMARY": 729, "RQ7_SECONDARY": 1992}
    assert manifest["counts"]["per_judge"] == {"gpt-4o-mini": 1590, "anthropic/claude-3-haiku": 1609, "deepseek/deepseek-chat": 1595, "meta-llama/llama-3.3-70b-instruct": 1655}
    assert len(ledger["historical_passes"]) == 24004
    assert Counter(row["classification"] for row in ledger["historical_passes"]) == {"SOURCE_CORRECT_REUSABLE": 17379, "CORRECTED_RERUN_REQUIRED": 6449, "HISTORICAL_ONLY_UNALIGNED": 176}


def test_full_manifest_mock_dry_run_is_network_free_and_payload_complete():
    with SessionLocal() as session:
        manifest, _ = build_plan(session)
    result = mock_dry_run(manifest)
    assert result == {"status": "PASS", "mock_transport_calls": 6449, "provider_calls": 0, "network": "DISABLED", "execution_authorized": False}
    assert len({row["idempotency_key"] for row in manifest["planned_passes"]}) == 6449
    assert all(row["rerun_reason"] == "CORRECTED_RERUN_REQUIRED" and row["fallbacks_allowed"] is False for row in manifest["planned_passes"])
    assert all(row["corrected_record_key"] for row in manifest["planned_passes"])
    variants = [row for row in manifest["planned_passes"] if row["rq_code"] in {"RQ4", "RQ5"}]
    assert variants and all(row["transform"] in {"VERBOSITY_REDUNDANCY", "FORMAT_ONLY"} for row in variants)
    assert all(row["source_corrected_payload"]["answer_a_sha256"] != row["prompt_sha256"] for row in manifest["planned_passes"])
    assert CONFIRMATION == "I_CONFIRM_SOURCE_CORRECTED_PAID_EXECUTION"


def test_durable_retry_resume_and_crash_transitions_fail_closed_in_isolation():
    engine = create_engine("sqlite://")
    DatasetVersion.__table__.create(engine)
    SourceCorrectedExecutionBatch.__table__.create(engine)
    SourceCorrectedExecutionSlot.__table__.create(engine)
    SourceCorrectedExecutionAttempt.__table__.create(engine)
    session = sessionmaker(bind=engine)()
    version = DatasetVersion(id=uuid4(), source_name="test", version="v", source_checksum="0" * 64, import_status="SUCCEEDED")
    batch = SourceCorrectedExecutionBatch(id=uuid4(), dataset_version_id=version.id, reconciliation_sha256=RECONCILIATION_SHA256, manifest_identity="test", manifest_sha256="1" * 64, global_hard_cap_usd=Decimal("10"), provider_hard_caps_json={"OPENAI": "10", "OPENROUTER": "10"}, status="MATERIALIZED", provenance_json={})
    slot = SourceCorrectedExecutionSlot(id=uuid4(), batch_id=batch.id, planned_pass_id="p", idempotency_key="i", rq_code="RQ1", judge_id="gpt-4o-mini", provider="OPENAI", route="OPENAI_DIRECT", payload_sha256="2" * 64, state="PENDING", estimated_input_tokens=100, estimated_output_tokens=10)
    session.add_all((version, batch, slot)); session.flush(); store = SourceCorrectedExecutionStore()
    attempt = store.reserve(session, batch.id, "p", owner="test"); assert attempt.state == "RESERVED"
    store.recover_crash(session, batch.id); assert session.get(SourceCorrectedExecutionSlot, slot.id).state == "PENDING"
    attempt = store.reserve(session, batch.id, "p", owner="test"); store.mark_sent(session, attempt, owner="test")
    store.recover_crash(session, batch.id); assert session.get(SourceCorrectedExecutionSlot, slot.id).state == "AMBIGUOUS"
    blocked = SourceCorrectedExecutionSlot(id=uuid4(), batch_id=batch.id, planned_pass_id="blocked", idempotency_key="blocked", rq_code="RQ1", judge_id="gpt-4o-mini", provider="OPENAI", route="OPENAI_DIRECT", payload_sha256="3" * 64, state="PENDING", estimated_input_tokens=100, estimated_output_tokens=10)
    batch.provider_hard_caps_json = {"OPENAI": "0", "OPENROUTER": "10"}; session.add(blocked); session.flush()
    with pytest.raises(SourceCorrectedPreflightError, match="budget guard"):
        store.reserve(session, batch.id, "blocked", owner="test")
    session.rollback(); session.close(); engine.dispose()
