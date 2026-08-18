"""Persist controlled variant text without contaminating legacy answers."""
from alembic import op
import sqlalchemy as sa

revision = "0006_controlled_variant_text"
down_revision = "0005_execution_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("counterfactual_variants") as batch:
        batch.add_column(sa.Column("experiment_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("variant_text", sa.Text(), nullable=True))
        batch.create_foreign_key("fk_variants_experiment", "experiments", ["experiment_id"], ["id"], ondelete="RESTRICT")
    with op.batch_alter_table("experimental_units") as batch:
        batch.add_column(sa.Column("counterfactual_variant_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key("fk_units_counterfactual_variant", "counterfactual_variants", ["counterfactual_variant_id"], ["id"], ondelete="RESTRICT")
        batch.create_index("ix_units_counterfactual_variant_id", ["counterfactual_variant_id"])


def downgrade() -> None:
    raise RuntimeError("Controlled execution migrations are forward-only.")
