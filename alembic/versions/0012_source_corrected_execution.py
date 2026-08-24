"""Add source-text-corrected execution planning ledger.

Revision ID: 0012_source_corrected_execution
Revises: 0011_multijudge_utc_metadata
"""
from alembic import op
import sqlalchemy as sa


revision = "0012_source_corrected_execution"
down_revision = "0011_multijudge_utc_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("source_corrected_execution_batches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_version_id", sa.Uuid(), sa.ForeignKey("dataset_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reconciliation_sha256", sa.String(64), nullable=False),
        sa.Column("manifest_identity", sa.String(160), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("global_hard_cap_usd", sa.Numeric(12, 8), nullable=False),
        sa.Column("provider_hard_caps_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False), sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table("source_corrected_execution_slots",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("batch_id", sa.Uuid(), sa.ForeignKey("source_corrected_execution_batches.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("planned_pass_id", sa.String(64), nullable=False, unique=True), sa.Column("idempotency_key", sa.String(64), nullable=False, unique=True),
        sa.Column("rq_code", sa.String(32), nullable=False), sa.Column("judge_id", sa.String(255), nullable=False), sa.Column("provider", sa.String(64), nullable=False), sa.Column("route", sa.String(255), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False), sa.Column("state", sa.String(32), nullable=False), sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("execution_owner", sa.String(128)), sa.Column("lease_expires_at", sa.DateTime(timezone=True)), sa.Column("estimated_input_tokens", sa.Integer(), nullable=False), sa.Column("estimated_output_tokens", sa.Integer(), nullable=False),
        sa.Column("reserved_usd", sa.Numeric(12, 8), nullable=False), sa.Column("actual_usd", sa.Numeric(12, 8)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("batch_id", "planned_pass_id", name="uq_source_corrected_batch_pass"),
    )
    op.create_table("source_corrected_execution_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("slot_id", sa.Uuid(), sa.ForeignKey("source_corrected_execution_slots.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("attempt_id", sa.String(64), nullable=False, unique=True), sa.Column("attempt_index", sa.Integer(), nullable=False), sa.Column("state", sa.String(32), nullable=False),
        sa.Column("failure_category", sa.String(64)), sa.Column("retry_decision", sa.String(32)), sa.Column("provider_response_id", sa.String(255)), sa.Column("input_tokens", sa.Integer()), sa.Column("output_tokens", sa.Integer()),
        sa.Column("reserved_usd", sa.Numeric(12, 8), nullable=False), sa.Column("actual_usd", sa.Numeric(12, 8)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("details_json", sa.JSON()),
        sa.UniqueConstraint("slot_id", "attempt_index", name="uq_source_corrected_attempt_index"),
    )
    op.create_table("source_corrected_reuse_ledger",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("batch_id", sa.Uuid(), sa.ForeignKey("source_corrected_execution_batches.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("historical_pass_identity", sa.String(128), nullable=False, unique=True), sa.Column("classification", sa.String(48), nullable=False), sa.Column("identity_sha256", sa.String(64), nullable=False), sa.Column("planned_pass_id", sa.String(64)), sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    raise RuntimeError("source-text corrected execution ledger is forward-only")
