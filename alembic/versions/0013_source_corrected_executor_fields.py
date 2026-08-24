"""Add durable result/provenance fields for corrected execution.

Revision ID: 0013_source_corrected_fields
Revises: 0012_source_corrected_execution
"""
from alembic import op
import sqlalchemy as sa


revision = "0013_source_corrected_fields"
down_revision = "0012_source_corrected_execution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("source_corrected_execution_slots", sa.Column("condition_code", sa.String(80)))
    op.add_column("source_corrected_execution_slots", sa.Column("requested_model", sa.String(255)))
    op.add_column("source_corrected_execution_slots", sa.Column("presentation", sa.String(16)))
    op.add_column("source_corrected_execution_slots", sa.Column("corrected_record_key", sa.String(64)))
    op.add_column("source_corrected_execution_slots", sa.Column("final_outcome", sa.String(32)))
    op.add_column("source_corrected_execution_slots", sa.Column("error_category", sa.String(64)))
    op.add_column("source_corrected_execution_slots", sa.Column("response_metadata_json", sa.JSON()))
    op.add_column("source_corrected_execution_slots", sa.Column("started_at", sa.DateTime(timezone=True)))
    op.add_column("source_corrected_execution_slots", sa.Column("completed_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    raise RuntimeError("source-text corrected executor fields are forward-only")
