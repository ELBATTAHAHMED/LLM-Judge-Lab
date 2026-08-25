"""Persist complete immutable source/prompt lineage for recovery slots.

Revision ID: 0015_recovery_lineage
Revises: 0014_source_corrected_recovery
"""
from alembic import op
import sqlalchemy as sa


revision = "0015_recovery_lineage"
down_revision = "0014_source_corrected_recovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("source_corrected_execution_slots", sa.Column("recovery_lineage_json", sa.JSON()))


def downgrade() -> None:
    raise RuntimeError("source-text corrected recovery lineage is forward-only")
