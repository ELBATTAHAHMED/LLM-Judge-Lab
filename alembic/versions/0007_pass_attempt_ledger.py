"""Durable pass-attempt state for retry and ambiguity recovery."""
from alembic import op
import sqlalchemy as sa

revision = "0007_pass_attempt_ledger"
down_revision = "0006_controlled_variant_text"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("pass_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pass_number", sa.Integer(), nullable=False),
        sa.Column("attempt_index", sa.Integer(), nullable=False),
        sa.Column("attempt_id", sa.String(64), nullable=False, unique=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("failure_category", sa.String(64)), sa.Column("retry_decision", sa.String(32)),
        sa.Column("provider_response_id", sa.String(255)), sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("completed_at", sa.DateTime()), sa.Column("details_json", sa.JSON()),
        sa.UniqueConstraint("run_id", "pass_number", "attempt_index", name="uq_pass_attempt_identity"),
        sa.CheckConstraint("state IN ('PENDING','IN_PROGRESS','SUCCEEDED','FAILED_RETRYABLE','FAILED_FINAL','AMBIGUOUS')", name="ck_pass_attempt_state"),
        sa.CheckConstraint("pass_number > 0 AND attempt_index >= 0", name="ck_pass_attempt_indices"),
    )
    op.create_index("ix_pass_attempts_run_pass", "pass_attempts", ["run_id", "pass_number"])


def downgrade() -> None:
    raise RuntimeError("Controlled execution migrations are forward-only.")
