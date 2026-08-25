"""Additive durable storage for the source-text-corrected execution plan.

These tables never point at or mutate historical controlled or multi-judge
execution rows.  They are intentionally a separate, pre-execution namespace.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class SourceCorrectedExecutionBatch(Base):
    __tablename__ = "source_corrected_execution_batches"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dataset_versions.id", ondelete="RESTRICT"), nullable=False)
    reconciliation_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_identity: Mapped[str] = mapped_column(String(160), nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    global_hard_cap_usd: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    provider_hard_caps_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="MATERIALIZED")
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SourceCorrectedExecutionSlot(Base):
    __tablename__ = "source_corrected_execution_slots"
    __table_args__ = (UniqueConstraint("batch_id", "planned_pass_id", name="uq_source_corrected_batch_pass"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_corrected_execution_batches.id", ondelete="RESTRICT"), nullable=False)
    planned_pass_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    rq_code: Mapped[str] = mapped_column(String(32), nullable=False)
    judge_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    route: Mapped[str] = mapped_column(String(255), nullable=False)
    condition_code: Mapped[str | None] = mapped_column(String(80))
    requested_model: Mapped[str | None] = mapped_column(String(255))
    presentation: Mapped[str | None] = mapped_column(String(16))
    corrected_record_key: Mapped[str | None] = mapped_column(String(64))
    # Recovery rows are additive replacements.  These fields retain the exact
    # historical logical-slot lineage without ever rewriting parent rows.
    recovery_manifest_sha256: Mapped[str | None] = mapped_column(String(64))
    original_logical_slot_id: Mapped[uuid.UUID | None] = mapped_column()
    original_planned_pass_id: Mapped[str | None] = mapped_column(String(64))
    recovery_reason: Mapped[str | None] = mapped_column(String(128))
    recovery_lineage_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    execution_owner: Mapped[str | None] = mapped_column(String(128))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_eligible_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estimated_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_usd: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False, default=Decimal("0"))
    actual_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    final_outcome: Mapped[str | None] = mapped_column(String(32))
    error_category: Mapped[str | None] = mapped_column(String(64))
    response_metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SourceCorrectedExecutionAttempt(Base):
    __tablename__ = "source_corrected_execution_attempts"
    __table_args__ = (UniqueConstraint("slot_id", "attempt_index", name="uq_source_corrected_attempt_index"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_corrected_execution_slots.id", ondelete="RESTRICT"), nullable=False)
    attempt_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    attempt_index: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    failure_category: Mapped[str | None] = mapped_column(String(64))
    retry_decision: Mapped[str | None] = mapped_column(String(32))
    provider_response_id: Mapped[str | None] = mapped_column(String(255))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    reserved_usd: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False, default=Decimal("0"))
    actual_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    details_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class SourceCorrectedReuseLedger(Base):
    __tablename__ = "source_corrected_reuse_ledger"
    __table_args__ = (UniqueConstraint("historical_pass_identity", name="uq_source_corrected_historical_pass"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_corrected_execution_batches.id", ondelete="RESTRICT"), nullable=False)
    historical_pass_identity: Mapped[str] = mapped_column(String(128), nullable=False)
    classification: Mapped[str] = mapped_column(String(48), nullable=False)
    identity_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    planned_pass_id: Mapped[str | None] = mapped_column(String(64))
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
