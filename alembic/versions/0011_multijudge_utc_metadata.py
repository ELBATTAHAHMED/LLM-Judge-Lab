"""Normalize multi-judge execution timestamps to timezone-aware UTC."""
from alembic import op


revision = "0011_multijudge_utc_metadata"
down_revision = "0010_multijudge_execution_lease"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite test databases have no distinct timezone-aware timestamp type.
        return

    # These rows were written by a UTC application clock into a database session
    # configured as Africa/Casablanca (+01:00). The exact one-hour correction is
    # bounded by the observed 3,500–3,700 second inversion window.
    op.execute("""
        UPDATE multijudge_execution_attempts
        SET started_at = started_at - INTERVAL '1 hour'
        WHERE completed_at IS NOT NULL
          AND completed_at < started_at
          AND started_at - completed_at BETWEEN INTERVAL '3500 seconds' AND INTERVAL '3700 seconds'
    """)

    timestamp_columns = {
        "multijudge_execution_batches": ("created_at", "updated_at"),
        "multijudge_execution_slots": ("created_at", "started_at", "completed_at", "updated_at", "lease_expires_at"),
        "multijudge_execution_attempts": ("started_at", "completed_at"),
    }
    for table, columns in timestamp_columns.items():
        for column in columns:
            op.execute(
                f'ALTER TABLE {table} ALTER COLUMN {column} TYPE TIMESTAMP WITH TIME ZONE '
                f'USING {column} AT TIME ZONE \'UTC\''
            )


def downgrade() -> None:
    raise RuntimeError("Multi-judge execution migrations are forward-only.")
