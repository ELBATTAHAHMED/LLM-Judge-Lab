"""Phase 8.5 controlled execution hardening; forward-only."""
from alembic import context, op
import sqlalchemy as sa

revision = "0005_execution_hardening"
down_revision = "0004_controlled_experiments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing controlled evidence is intentionally absent.  PostgreSQL needs
    # a real ALTER; SQLite test databases are rebuilt by Alembic batch mode.
    with op.batch_alter_table("experimental_units") as batch:
        batch.alter_column("presentation_order", existing_type=sa.String(2), type_=sa.String(32), existing_nullable=False)
    # ``runs`` is empty in the recovered pre-execution database.  SQLite
    # requires table recreation for a new FK; PostgreSQL can use ALTER TABLE.
    with op.batch_alter_table("runs") as batch:
        batch.add_column(sa.Column("experimental_unit_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key("fk_runs_experimental_unit", "experimental_units", ["experimental_unit_id"], ["id"], ondelete="RESTRICT")
        batch.create_index("ix_runs_experimental_unit_id", ["experimental_unit_id"])
    # No historical run is controlled evidence.  A populated old database
    # must be explicitly migrated/backfilled rather than silently linked.
    if not context.is_offline_mode() and op.get_bind().execute(sa.text("SELECT COUNT(*) FROM runs")).scalar() != 0:
        raise RuntimeError("Cannot harden a populated runs table without an explicit provenance backfill.")
    with op.batch_alter_table("runs") as batch:
        batch.alter_column("experimental_unit_id", existing_type=sa.Uuid(), nullable=False)


def downgrade() -> None:
    raise RuntimeError("Controlled execution migrations are forward-only.")
