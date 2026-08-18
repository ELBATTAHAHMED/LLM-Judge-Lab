"""Persist provider route provenance and distinct controlled outcomes.

Forward-only: legacy tables/rows are untouched and nullable columns preserve
the recovered history.
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_execution_provenance"
down_revision = "0007_pass_attempt_ledger"
branch_labels = None
depends_on = None

def upgrade() -> None:
    # SQLite requires batch recreation for named CHECK constraints; PostgreSQL
    # receives the same forward-only semantic change.
    with op.batch_alter_table("passes") as batch:
        batch.drop_constraint("ck_pass_parse_status", type_="check")
        batch.create_check_constraint("ck_pass_parse_status", "parse_status IN ('PARSED', 'INVALID_JSON', 'SCHEMA_ERROR', 'MISSING_RESPONSE', 'PROVIDER_ERROR', 'TIMEOUT', 'UNSUPPORTED', 'INTERNAL_ERROR', 'INVALID', 'MISSING', 'PARSING_ERROR', 'REFUSAL')")
    op.add_column("passes", sa.Column("outcome", sa.String(32), nullable=True))
    op.add_column("passes", sa.Column("route_provenance_json", sa.JSON(), nullable=True))
    op.add_column("passes", sa.Column("presentation_provenance_json", sa.JSON(), nullable=True))
    op.add_column("pass_attempts", sa.Column("route_provenance_json", sa.JSON(), nullable=True))
    op.add_column("pass_attempts", sa.Column("input_tokens", sa.Integer(), nullable=True))
    op.add_column("pass_attempts", sa.Column("output_tokens", sa.Integer(), nullable=True))
    op.add_column("pass_attempts", sa.Column("estimated_usd", sa.Numeric(12, 8), nullable=True))
    op.add_column("pass_attempts", sa.Column("actual_usd", sa.Numeric(12, 8), nullable=True))

def downgrade() -> None:
    raise RuntimeError("Controlled execution migrations are forward-only.")
