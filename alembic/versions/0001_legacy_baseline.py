"""Reconstruct the original legacy evidence tables.

This migration is intentionally additive historical source.  It is never run
against the already-upgraded research database in Phase 1.
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_legacy_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prompts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
    )
    op.create_table(
        "answers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("prompt_id", sa.Integer(), sa.ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column("format_type", sa.String(50), server_default="plain_text"),
    )
    op.create_table(
        "human_preferences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("prompt_id", sa.Integer(), sa.ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("answer_a_id", sa.Integer(), sa.ForeignKey("answers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("answer_b_id", sa.Integer(), sa.ForeignKey("answers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("winner_id", sa.Integer(), sa.ForeignKey("answers.id", ondelete="SET NULL")),
    )
    op.create_table(
        "judge_decisions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("prompt_id", sa.Integer(), sa.ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("judge_model_name", sa.String(100), nullable=False),
        sa.Column("answer_a_id", sa.Integer(), sa.ForeignKey("answers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("answer_b_id", sa.Integer(), sa.ForeignKey("answers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position_a_id", sa.Integer(), sa.ForeignKey("answers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("winner_id", sa.Integer(), sa.ForeignKey("answers.id", ondelete="SET NULL")),
        sa.Column("reasoning", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("judge_decisions")
    op.drop_table("human_preferences")
    op.drop_table("answers")
    op.drop_table("prompts")
