"""Dedicated ORM storage for frozen multi-judge execution operations only."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base


class MultiJudgeExecutionBatch(Base):
    __tablename__ = "multijudge_execution_batches"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    protocol_id: Mapped[str] = mapped_column(String(128), nullable=False)
    protocol_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_id: Mapped[str] = mapped_column(String(128), nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    hard_cap_usd: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="MATERIALIZED")
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MultiJudgeExecutionSlot(Base):
    __tablename__ = "multijudge_execution_slots"
    __table_args__ = (
        UniqueConstraint("batch_id", "canonical_pair_id", "judge_id", name="uq_multijudge_pair_judge"),
        CheckConstraint("presentation IN ('AB', 'BA')", name="ck_multijudge_presentation"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("multijudge_execution_batches.id", ondelete="RESTRICT"), nullable=False)
    canonical_pair_id: Mapped[str] = mapped_column(String(64), nullable=False)
    planned_pass_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    judge_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_model: Mapped[str] = mapped_column(String(255), nullable=False)
    route: Mapped[str] = mapped_column(String(128), nullable=False)
    presentation: Mapped[str] = mapped_column(String(2), nullable=False)
    original_answer_1_id: Mapped[int] = mapped_column(Integer, nullable=False)
    original_answer_2_id: Mapped[int] = mapped_column(Integer, nullable=False)
    displayed_a_answer_id: Mapped[int] = mapped_column(Integer, nullable=False)
    displayed_b_answer_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    final_outcome: Mapped[str | None] = mapped_column(String(32))
    mapped_vote: Mapped[str | None] = mapped_column(String(32))
    raw_response_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    execution_owner: Mapped[str | None] = mapped_column(String(64))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MultiJudgeExecutionAttempt(Base):
    __tablename__ = "multijudge_execution_attempts"
    __table_args__ = (UniqueConstraint("slot_id", "attempt_index", name="uq_multijudge_slot_attempt"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("multijudge_execution_slots.id", ondelete="RESTRICT"), nullable=False)
    attempt_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    attempt_index: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    failure_category: Mapped[str | None] = mapped_column(String(64))
    retry_decision: Mapped[str | None] = mapped_column(String(32))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    reserved_usd: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False, default=Decimal("0"))
    actual_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    provider_response_id: Mapped[str | None] = mapped_column(String(255))
    effective_model: Mapped[str | None] = mapped_column(String(255))
    route_provenance_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    details_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
