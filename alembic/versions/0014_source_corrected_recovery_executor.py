"""Add additive lineage and durable scheduling fields for recovery execution.

Revision ID: 0014_source_corrected_recovery
Revises: 0013_source_corrected_fields
"""
from alembic import op
import sqlalchemy as sa


revision = "0014_source_corrected_recovery"
down_revision = "0013_source_corrected_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("source_corrected_execution_slots", sa.Column("recovery_manifest_sha256", sa.String(64)))
    op.add_column("source_corrected_execution_slots", sa.Column("original_logical_slot_id", sa.Uuid()))
    op.add_column("source_corrected_execution_slots", sa.Column("original_planned_pass_id", sa.String(64)))
    op.add_column("source_corrected_execution_slots", sa.Column("recovery_reason", sa.String(128)))
    op.add_column("source_corrected_execution_slots", sa.Column("next_eligible_at", sa.DateTime(timezone=True)))
    op.create_index("ix_source_corrected_recovery_next_eligible", "source_corrected_execution_slots", ["batch_id", "state", "next_eligible_at"])


def downgrade() -> None:
    raise RuntimeError("source-text corrected recovery executor fields are forward-only")
