"""Add durable ownership leases for in-flight multi-judge slots."""
from alembic import op
import sqlalchemy as sa


revision = "0010_multijudge_execution_lease"
down_revision = "0009_multijudge_execution_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("multijudge_execution_slots", sa.Column("execution_owner", sa.String(64), nullable=True))
    op.add_column("multijudge_execution_slots", sa.Column("lease_expires_at", sa.DateTime(), nullable=True))
    op.create_index("ix_multijudge_slots_lease", "multijudge_execution_slots", ["batch_id", "status", "lease_expires_at"])


def downgrade() -> None:
    raise RuntimeError("Multi-judge execution migrations are forward-only.")
