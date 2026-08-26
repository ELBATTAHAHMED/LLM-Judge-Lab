"""ORM mapping for the recovered controlled-experiment schema.

These models map the already-existing PostgreSQL revision
``0004_controlled_experiments``.  They are intentionally separate from the
legacy runner models so Phase 1 does not change historical write behaviour.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


UUID = uuid.UUID


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("source_name", "version", "source_checksum", name="uq_dataset_source_version_checksum"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[Optional[str]] = mapped_column(String(128))
    license_text: Mapped[Optional[str]] = mapped_column(Text)
    source_uri: Mapped[Optional[str]] = mapped_column(Text)
    source_checksum: Mapped[Optional[str]] = mapped_column(String(64))
    checksum_algorithm: Mapped[Optional[str]] = mapped_column(String(32))
    imported_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    import_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    imported_prompt_count: Mapped[Optional[int]] = mapped_column(Integer)
    imported_answer_count: Mapped[Optional[int]] = mapped_column(Integer)
    imported_annotation_count: Mapped[Optional[int]] = mapped_column(Integer)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    experiment_name: Mapped[str] = mapped_column(String(255), nullable=False)
    research_question: Mapped[str] = mapped_column(Text, nullable=False)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_version_id: Mapped[UUID] = mapped_column(ForeignKey("dataset_versions.id", ondelete="RESTRICT"), nullable=False)
    mitigation_strategy: Mapped[str] = mapped_column(String(100), nullable=False, default="NONE")
    analysis_version: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PLANNED")
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    dataset_version: Mapped[DatasetVersion] = relationship()
    conditions: Mapped[list["ExperimentalCondition"]] = relationship(back_populates="experiment")
    manifests: Mapped[list["ExperimentManifest"]] = relationship(back_populates="experiment")


class ExperimentalCondition(Base):
    __tablename__ = "experimental_conditions"
    __table_args__ = (UniqueConstraint("experiment_id", "condition_code", name="uq_phase4_condition_experiment_code"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[UUID] = mapped_column(ForeignKey("experiments.id", ondelete="RESTRICT"), nullable=False)
    condition_code: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    condition_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    protocol_version: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_template_version: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    experiment: Mapped[Experiment] = relationship(back_populates="conditions")


class ExperimentManifest(Base):
    __tablename__ = "experiment_manifests"
    __table_args__ = (UniqueConstraint("experiment_id", "manifest_sha256", name="uq_phase4_manifest_experiment_sha"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[UUID] = mapped_column(ForeignKey("experiments.id", ondelete="RESTRICT"), nullable=False)
    rq_code: Mapped[str] = mapped_column(String(8), nullable=False)
    protocol_version: Mapped[str] = mapped_column(String(80), nullable=False)
    analysis_version: Mapped[str] = mapped_column(String(80), nullable=False)
    dataset_snapshot_id: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PLANNED")
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    frozen_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    experiment: Mapped[Experiment] = relationship(back_populates="manifests")


class ExperimentalUnit(Base):
    __tablename__ = "experimental_units"
    __table_args__ = (UniqueConstraint("unit_fingerprint", name="uq_phase4_unit_fingerprint"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[UUID] = mapped_column(ForeignKey("experiments.id", ondelete="RESTRICT"), nullable=False)
    manifest_id: Mapped[UUID] = mapped_column(ForeignKey("experiment_manifests.id", ondelete="RESTRICT"), nullable=False)
    condition_id: Mapped[UUID] = mapped_column(ForeignKey("experimental_conditions.id", ondelete="RESTRICT"), nullable=False)
    counterfactual_variant_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("counterfactual_variants.id", ondelete="RESTRICT"))
    prompt_id: Mapped[int] = mapped_column(ForeignKey("prompts.id", ondelete="RESTRICT"), nullable=False)
    answer_a_id: Mapped[int] = mapped_column(ForeignKey("answers.id", ondelete="RESTRICT"), nullable=False)
    answer_b_id: Mapped[int] = mapped_column(ForeignKey("answers.id", ondelete="RESTRICT"), nullable=False)
    answer_a_author_id: Mapped[Optional[str]] = mapped_column(String(255))
    answer_b_author_id: Mapped[Optional[str]] = mapped_column(String(255))
    human_label: Mapped[Optional[str]] = mapped_column(String(16))
    prompt_category: Mapped[str] = mapped_column(String(100), nullable=False)
    condition_code: Mapped[str] = mapped_column(String(80), nullable=False)
    # Phase 8.5: ``AB_BA`` and ``SELF_A`` are scientific protocol values, not
    # two-character display labels.  Keep this permissive enough for future
    # versioned orders while the planner validates their meaning.
    presentation_order: Mapped[str] = mapped_column(String(32), nullable=False)
    judge_model: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_model: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_template_version: Mapped[str] = mapped_column(String(255), nullable=False)
    temperature: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    top_p: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    seed: Mapped[Optional[int]] = mapped_column(Integer)
    repetition_index: Mapped[int] = mapped_column(Integer, nullable=False)
    randomization_block: Mapped[str] = mapped_column(String(255), nullable=False)
    data_split: Mapped[str] = mapped_column(String(64), nullable=False)
    inclusion_status: Mapped[str] = mapped_column(String(32), nullable=False)
    exclusion_reason: Mapped[Optional[str]] = mapped_column(Text)
    pairing_key: Mapped[Optional[str]] = mapped_column(String(64))
    unit_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class CounterfactualVariant(Base):
    __tablename__ = "counterfactual_variants"
    __table_args__ = (UniqueConstraint("original_answer_id", "condition_code", "transformation_version", "variant_checksum", name="uq_phase4_variant_identity"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    original_answer_id: Mapped[int] = mapped_column(ForeignKey("answers.id", ondelete="RESTRICT"), nullable=False)
    experiment_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("experiments.id", ondelete="RESTRICT"))
    variant_answer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("answers.id", ondelete="RESTRICT"))
    # Variant text is controlled-planning provenance, never a legacy answer.
    variant_text: Mapped[Optional[str]] = mapped_column(Text)
    condition_code: Mapped[str] = mapped_column(String(80), nullable=False)
    transformation_method: Mapped[str] = mapped_column(String(80), nullable=False)
    transformation_version: Mapped[str] = mapped_column(String(80), nullable=False)
    original_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    variant_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    original_word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    variant_word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    original_token_estimate: Mapped[int] = mapped_column(Integer, nullable=False)
    variant_token_estimate: Mapped[int] = mapped_column(Integer, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    validation_details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class ControlledRun(Base):
    __tablename__ = "runs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="runs_idempotency_key_key"),
        UniqueConstraint("legacy_decision_id", name="runs_legacy_decision_id_key"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[UUID] = mapped_column(ForeignKey("experiments.id", ondelete="RESTRICT"), nullable=False)
    experimental_unit_id: Mapped[UUID] = mapped_column(ForeignKey("experimental_units.id", ondelete="RESTRICT"), nullable=False)
    prompt_id: Mapped[int] = mapped_column(ForeignKey("prompts.id", ondelete="RESTRICT"), nullable=False)
    original_answer_a_id: Mapped[int] = mapped_column(ForeignKey("answers.id", ondelete="RESTRICT"), nullable=False)
    original_answer_b_id: Mapped[int] = mapped_column(ForeignKey("answers.id", ondelete="RESTRICT"), nullable=False)
    judge_name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    requested_model: Mapped[str] = mapped_column(String(255), nullable=False)
    effective_model: Mapped[Optional[str]] = mapped_column(String(255))
    model_version: Mapped[Optional[str]] = mapped_column(String(255))
    prompt_template_version: Mapped[Optional[str]] = mapped_column(String(255))
    temperature: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    top_p: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    seed: Mapped[Optional[int]] = mapped_column(Integer)
    repetition_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    run_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="STANDARD")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    api_response_id: Mapped[Optional[str]] = mapped_column(String(255))
    error_code: Mapped[Optional[str]] = mapped_column(String(100))
    error_details: Mapped[Optional[str]] = mapped_column(Text)
    final_result_type: Mapped[Optional[str]] = mapped_column(String(16))
    final_winner_answer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("answers.id", ondelete="RESTRICT"))
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    parent_run_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("runs.id", ondelete="RESTRICT"))
    legacy_decision_id: Mapped[Optional[int]] = mapped_column(ForeignKey("judge_decisions.id", ondelete="SET NULL"))
    provider_model: Mapped[Optional[str]] = mapped_column(String(255))
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    final_parse_status: Mapped[Optional[str]] = mapped_column(String(32))
    final_criteria: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    final_confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 5))
    final_explanation: Mapped[Optional[str]] = mapped_column(Text)
    dual_pass_classification: Mapped[Optional[str]] = mapped_column(String(40))

    experimental_unit: Mapped[ExperimentalUnit] = relationship(foreign_keys=[experimental_unit_id])
    passes: Mapped[list["RunPass"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class RunPass(Base):
    __tablename__ = "passes"
    __table_args__ = (UniqueConstraint("run_id", "pass_number", name="uq_pass_run_number"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    pass_number: Mapped[int] = mapped_column(Integer, nullable=False)
    presented_answer_a_id: Mapped[int] = mapped_column(ForeignKey("answers.id", ondelete="RESTRICT"), nullable=False)
    presented_answer_b_id: Mapped[int] = mapped_column(ForeignKey("answers.id", ondelete="RESTRICT"), nullable=False)
    raw_verdict: Mapped[str] = mapped_column(String(16), nullable=False)
    winner_answer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("answers.id", ondelete="RESTRICT"))
    parse_status: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 5))
    raw_provider_response: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    reasoning_summary: Mapped[Optional[str]] = mapped_column(Text)
    api_response_id: Mapped[Optional[str]] = mapped_column(String(255))
    effective_model: Mapped[Optional[str]] = mapped_column(String(255))
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    criteria_scores: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    provider_model: Mapped[Optional[str]] = mapped_column(String(255))
    model_version: Mapped[Optional[str]] = mapped_column(String(255))
    # v0008: durable scientific outcome and observed provider-route identity.
    outcome: Mapped[Optional[str]] = mapped_column(String(32))
    route_provenance_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    presentation_provenance_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)

    run: Mapped[ControlledRun] = relationship(back_populates="passes")


class PassAttempt(Base):
    """Durable provider-attempt ledger; one scientific pass can have retries."""
    __tablename__ = "pass_attempts"
    __table_args__ = (UniqueConstraint("run_id", "pass_number", "attempt_index", name="uq_pass_attempt_identity"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    pass_number: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_index: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    failure_category: Mapped[Optional[str]] = mapped_column(String(64))
    retry_decision: Mapped[Optional[str]] = mapped_column(String(32))
    provider_response_id: Mapped[Optional[str]] = mapped_column(String(255))
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    details_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    route_provenance_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    estimated_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 8))
    actual_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 8))


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[UUID] = mapped_column(ForeignKey("experiments.id", ondelete="RESTRICT"), nullable=False)
    manifest_id: Mapped[UUID] = mapped_column(ForeignKey("experiment_manifests.id", ondelete="RESTRICT"), nullable=False)
    rq_code: Mapped[str] = mapped_column(String(8), nullable=False)
    analysis_version: Mapped[str] = mapped_column(String(80), nullable=False)
    analysis_seed: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
