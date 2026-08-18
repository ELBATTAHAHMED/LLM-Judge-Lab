"""Recover manifest, unit, variant, and analysis provenance tables."""
from alembic import op
import sqlalchemy as sa

revision = "0004_controlled_experiments"
down_revision = "0003_evaluation_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "experiment_manifests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("experiment_id", sa.Uuid(), sa.ForeignKey("experiments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("rq_code", sa.String(8), nullable=False), sa.Column("protocol_version", sa.String(80), nullable=False),
        sa.Column("analysis_version", sa.String(80), nullable=False), sa.Column("dataset_snapshot_id", sa.String(255), nullable=False),
        sa.Column("dataset_checksum", sa.String(64), nullable=False), sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PLANNED"), sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")), sa.Column("frozen_at", sa.DateTime()),
        sa.UniqueConstraint("experiment_id", "manifest_sha256", name="uq_phase4_manifest_experiment_sha"),
        sa.CheckConstraint("status IN ('PLANNED', 'FROZEN', 'INVALIDATED')", name="ck_phase4_manifest_status"),
    )
    op.create_index("ix_phase4_manifests_rq", "experiment_manifests", ["rq_code"])
    op.create_table(
        "experimental_units",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("experiment_id", sa.Uuid(), sa.ForeignKey("experiments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("manifest_id", sa.Uuid(), sa.ForeignKey("experiment_manifests.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("condition_id", sa.Uuid(), sa.ForeignKey("experimental_conditions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("prompt_id", sa.Integer(), sa.ForeignKey("prompts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("answer_a_id", sa.Integer(), sa.ForeignKey("answers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("answer_b_id", sa.Integer(), sa.ForeignKey("answers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("answer_a_author_id", sa.String(255)), sa.Column("answer_b_author_id", sa.String(255)), sa.Column("human_label", sa.String(16)),
        sa.Column("prompt_category", sa.String(100), nullable=False), sa.Column("condition_code", sa.String(80), nullable=False),
        sa.Column("presentation_order", sa.String(2), nullable=False), sa.Column("judge_model", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False), sa.Column("provider_model", sa.String(255), nullable=False),
        sa.Column("prompt_template_version", sa.String(255), nullable=False), sa.Column("temperature", sa.Numeric(5,4)), sa.Column("top_p", sa.Numeric(5,4)), sa.Column("seed", sa.Integer()),
        sa.Column("repetition_index", sa.Integer(), nullable=False), sa.Column("randomization_block", sa.String(255), nullable=False),
        sa.Column("data_split", sa.String(64), nullable=False), sa.Column("inclusion_status", sa.String(32), nullable=False), sa.Column("exclusion_reason", sa.Text()),
        sa.Column("pairing_key", sa.String(64)), sa.Column("unit_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("unit_fingerprint", name="uq_phase4_unit_fingerprint"),
    )
    for name, cols in {"ix_phase4_units_manifest":["manifest_id"], "ix_phase4_units_pairing":["pairing_key"], "ix_phase4_units_prompt":["prompt_id"]}.items(): op.create_index(name, "experimental_units", cols)
    op.create_table(
        "counterfactual_variants",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("original_answer_id", sa.Integer(), sa.ForeignKey("answers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("variant_answer_id", sa.Integer(), sa.ForeignKey("answers.id", ondelete="RESTRICT")), sa.Column("condition_code", sa.String(80), nullable=False),
        sa.Column("transformation_method", sa.String(80), nullable=False), sa.Column("transformation_version", sa.String(80), nullable=False),
        sa.Column("original_checksum", sa.String(64), nullable=False), sa.Column("variant_checksum", sa.String(64), nullable=False),
        sa.Column("original_word_count", sa.Integer(), nullable=False), sa.Column("variant_word_count", sa.Integer(), nullable=False),
        sa.Column("original_token_estimate", sa.Integer(), nullable=False), sa.Column("variant_token_estimate", sa.Integer(), nullable=False),
        sa.Column("validation_status", sa.String(32), nullable=False), sa.Column("validation_details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("original_answer_id", "condition_code", "transformation_version", "variant_checksum", name="uq_phase4_variant_identity"),
    )
    op.create_index("ix_phase4_variants_original", "counterfactual_variants", ["original_answer_id"])
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("experiment_id", sa.Uuid(), sa.ForeignKey("experiments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("manifest_id", sa.Uuid(), sa.ForeignKey("experiment_manifests.id", ondelete="RESTRICT"), nullable=False), sa.Column("rq_code", sa.String(8), nullable=False),
        sa.Column("analysis_version", sa.String(80), nullable=False), sa.Column("analysis_seed", sa.Integer(), nullable=False), sa.Column("status", sa.String(32), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_phase4_analysis_manifest", "analysis_runs", ["manifest_id"])


def downgrade() -> None:
    raise RuntimeError("Phase 1 recovery migrations are forward-only to protect research evidence.")
