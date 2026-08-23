"""Add dedicated durable storage for the frozen multi-judge execution.

This is deliberately separate from the historical controlled ``runs`` /
``passes`` tables: it stores only operational scheduling and future provider
attempt provenance for ``multi-judge-consensus-v1``.
"""
from alembic import op
import sqlalchemy as sa


revision = "0009_multijudge_execution_ledger"
down_revision = "0008_execution_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "multijudge_execution_batches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("protocol_id", sa.String(128), nullable=False),
        sa.Column("protocol_sha256", sa.String(64), nullable=False),
        sa.Column("manifest_id", sa.String(128), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("hard_cap_usd", sa.Numeric(12, 8), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="MATERIALIZED"),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "multijudge_execution_slots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("batch_id", sa.Uuid(), sa.ForeignKey("multijudge_execution_batches.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("canonical_pair_id", sa.String(64), nullable=False),
        sa.Column("planned_pass_id", sa.String(64), nullable=False, unique=True),
        sa.Column("idempotency_key", sa.String(64), nullable=False, unique=True),
        sa.Column("judge_id", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("requested_model", sa.String(255), nullable=False),
        sa.Column("route", sa.String(128), nullable=False),
        sa.Column("presentation", sa.String(2), nullable=False),
        sa.Column("original_answer_1_id", sa.Integer(), nullable=False),
        sa.Column("original_answer_2_id", sa.Integer(), nullable=False),
        sa.Column("displayed_a_answer_id", sa.Integer(), nullable=False),
        sa.Column("displayed_b_answer_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("final_outcome", sa.String(32)),
        sa.Column("mapped_vote", sa.String(32)),
        sa.Column("raw_response_metadata", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("batch_id", "canonical_pair_id", "judge_id", name="uq_multijudge_pair_judge"),
        sa.CheckConstraint("presentation IN ('AB', 'BA')", name="ck_multijudge_presentation"),
    )
    op.create_index("ix_multijudge_slots_batch_status", "multijudge_execution_slots", ["batch_id", "status"])
    op.create_table(
        "multijudge_execution_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slot_id", sa.Uuid(), sa.ForeignKey("multijudge_execution_slots.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("attempt_id", sa.String(64), nullable=False, unique=True),
        sa.Column("attempt_index", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("failure_category", sa.String(64)),
        sa.Column("retry_decision", sa.String(32)),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("reserved_usd", sa.Numeric(12, 8), nullable=False, server_default="0"),
        sa.Column("actual_usd", sa.Numeric(12, 8)),
        sa.Column("provider_response_id", sa.String(255)),
        sa.Column("effective_model", sa.String(255)),
        sa.Column("route_provenance_json", sa.JSON()),
        sa.Column("details_json", sa.JSON()),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime()),
        sa.UniqueConstraint("slot_id", "attempt_index", name="uq_multijudge_slot_attempt"),
    )
    op.create_index("ix_multijudge_attempts_slot", "multijudge_execution_attempts", ["slot_id"])


def downgrade() -> None:
    raise RuntimeError("Multi-judge execution ledger is forward-only.")
