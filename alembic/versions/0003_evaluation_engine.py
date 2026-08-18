"""Recover auditable run/pass persistence.

The physical database is the contract: these tables and constraint semantics
are reconstructed from its revision 0004 inspection, not inferred from legacy
JudgeDecision rows.
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_evaluation_engine"
down_revision = "0002_phase2_provenance"
branch_labels = None
depends_on = None


RESULT_TYPES = "final_result_type IN ('ANSWER_A', 'ANSWER_B', 'TIE', 'UNKNOWN', 'ERROR', 'PARTIAL')"
RUN_STATUSES = "status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'PARTIAL', 'FAILED', 'SKIPPED', 'IMPORTED_LEGACY')"
PASS_VERDICTS = "raw_verdict IN ('ANSWER_A', 'ANSWER_B', 'TIE', 'UNKNOWN', 'ERROR')"
PARSE_STATUSES = "parse_status IN ('PARSED', 'INVALID_JSON', 'SCHEMA_ERROR', 'MISSING_RESPONSE', 'PROVIDER_ERROR', 'TIMEOUT', 'UNSUPPORTED', 'INTERNAL_ERROR', 'INVALID', 'MISSING', 'PARSING_ERROR')"


def upgrade() -> None:
    op.create_table(
        "experiments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("experiment_name", sa.String(255), nullable=False),
        sa.Column("research_question", sa.Text(), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=False),
        sa.Column("dataset_version_id", sa.Uuid(), sa.ForeignKey("dataset_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("mitigation_strategy", sa.String(100), nullable=False, server_default="NONE"),
        sa.Column("analysis_version", sa.String(255)),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False, server_default="PLANNED"),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("length(trim(experiment_name)) > 0", name="ck_experiment_name_not_blank"),
        sa.CheckConstraint("length(trim(research_question)) > 0", name="ck_experiment_question_not_blank"),
        sa.CheckConstraint("length(trim(hypothesis)) > 0", name="ck_experiment_hypothesis_not_blank"),
        sa.CheckConstraint("length(trim(mitigation_strategy)) > 0", name="ck_experiment_strategy_not_blank"),
        sa.CheckConstraint("status IN ('PLANNED', 'RUNNING', 'COMPLETED', 'FAILED', 'ARCHIVED')", name="ck_experiment_status"),
    )
    for name, cols in {
        "ix_experiments_created_at": ["created_at"], "ix_experiments_dataset_version_id": ["dataset_version_id"],
        "ix_experiments_research_question": ["research_question"], "ix_experiments_status": ["status"],
    }.items(): op.create_index(name, "experiments", cols)

    op.create_table(
        "experimental_conditions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("experiment_id", sa.Uuid(), sa.ForeignKey("experiments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("condition_code", sa.String(80), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("condition_json", sa.JSON(), nullable=False),
        sa.Column("protocol_version", sa.String(80), nullable=False),
        sa.Column("prompt_template_version", sa.String(255)),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("experiment_id", "condition_code", name="uq_phase4_condition_experiment_code"),
    )
    op.create_index("ix_phase4_conditions_experiment", "experimental_conditions", ["experiment_id"])

    op.create_table(
        "runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("experiment_id", sa.Uuid(), sa.ForeignKey("experiments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("prompt_id", sa.Integer(), sa.ForeignKey("prompts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("original_answer_a_id", sa.Integer(), sa.ForeignKey("answers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("original_answer_b_id", sa.Integer(), sa.ForeignKey("answers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("judge_name", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("requested_model", sa.String(255), nullable=False),
        sa.Column("effective_model", sa.String(255)),
        sa.Column("model_version", sa.String(255)),
        sa.Column("prompt_template_version", sa.String(255)),
        sa.Column("temperature", sa.Numeric(5, 4)), sa.Column("top_p", sa.Numeric(5, 4)), sa.Column("seed", sa.Integer()),
        sa.Column("repetition_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("run_kind", sa.String(32), nullable=False, server_default="STANDARD"),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("started_at", sa.DateTime()), sa.Column("completed_at", sa.DateTime()), sa.Column("latency_ms", sa.Integer()),
        sa.Column("api_response_id", sa.String(255)), sa.Column("error_code", sa.String(100)), sa.Column("error_details", sa.Text()),
        sa.Column("final_result_type", sa.String(16)),
        sa.Column("final_winner_answer_id", sa.Integer(), sa.ForeignKey("answers.id", ondelete="RESTRICT")),
        sa.Column("idempotency_key", sa.String(64), nullable=False), sa.Column("metadata_json", sa.JSON()),
        sa.Column("parent_run_id", sa.Uuid(), sa.ForeignKey("runs.id", ondelete="RESTRICT")),
        sa.Column("legacy_decision_id", sa.Integer(), sa.ForeignKey("judge_decisions.id", ondelete="SET NULL")),
        sa.Column("provider_model", sa.String(255)), sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("final_parse_status", sa.String(32)), sa.Column("final_criteria", sa.JSON()),
        sa.Column("final_confidence", sa.Numeric(6, 5)), sa.Column("final_explanation", sa.Text()),
        sa.Column("dual_pass_classification", sa.String(40)),
        sa.UniqueConstraint("idempotency_key", name="runs_idempotency_key_key"),
        sa.UniqueConstraint("legacy_decision_id", name="runs_legacy_decision_id_key"),
        sa.CheckConstraint("original_answer_a_id <> original_answer_b_id", name="ck_run_original_answers_distinct"),
        sa.CheckConstraint("length(trim(judge_name)) > 0", name="ck_run_judge_name_not_blank"),
        sa.CheckConstraint("length(trim(provider)) > 0", name="ck_run_provider_not_blank"),
        sa.CheckConstraint("length(trim(requested_model)) > 0", name="ck_run_requested_model_not_blank"),
        sa.CheckConstraint("repetition_index >= 0", name="ck_run_repetition_nonnegative"),
        sa.CheckConstraint("temperature IS NULL OR (temperature >= 0 AND temperature <= 2)", name="ck_run_temperature_range"),
        sa.CheckConstraint("top_p IS NULL OR (top_p >= 0 AND top_p <= 1)", name="ck_run_top_p_range"),
        sa.CheckConstraint("latency_ms IS NULL OR latency_ms >= 0", name="ck_run_latency_nonnegative"),
        sa.CheckConstraint("completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at", name="ck_run_completed_after_started"),
        sa.CheckConstraint(RUN_STATUSES, name="ck_run_status"),
        sa.CheckConstraint("run_kind IN ('STANDARD', 'CALIBRATED_DUAL_PASS', 'ENSEMBLE_PARENT', 'ENSEMBLE_CHILD', 'STOCHASTIC', 'PERTURBATION', 'ABLATION')", name="ck_run_kind"),
        sa.CheckConstraint("dual_pass_classification IS NULL OR dual_pass_classification IN ('SAME_DECISIVE_WINNER', 'DECISIVE_FLIP', 'CONSISTENT_TIE', 'TIE_DISAGREEMENT', 'CONSISTENT_UNKNOWN', 'UNKNOWN_ERROR_DISAGREEMENT', 'PARTIAL_EXECUTION', 'BOTH_FAILED')", name="ck_run_dual_pass_classification"),
        sa.CheckConstraint("final_result_type IS NULL OR " + RESULT_TYPES, name="ck_run_final_result_type"),
        sa.CheckConstraint("final_result_type IS NULL OR ((final_result_type IN ('ANSWER_A', 'ANSWER_B')) = (final_winner_answer_id IS NOT NULL))", name="ck_run_final_result_winner_null"),
    )
    for name, cols in {
        "ix_runs_created_at":["created_at"], "ix_runs_experiment_id":["experiment_id"], "ix_runs_original_answer_a_id":["original_answer_a_id"],
        "ix_runs_original_answer_b_id":["original_answer_b_id"], "ix_runs_parent_run_id":["parent_run_id"], "ix_runs_prompt_id":["prompt_id"],
        "ix_runs_requested_model":["requested_model"], "ix_runs_status":["status"],
    }.items(): op.create_index(name, "runs", cols)

    op.create_table(
        "passes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pass_number", sa.Integer(), nullable=False),
        sa.Column("presented_answer_a_id", sa.Integer(), sa.ForeignKey("answers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("presented_answer_b_id", sa.Integer(), sa.ForeignKey("answers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("raw_verdict", sa.String(16), nullable=False),
        sa.Column("winner_answer_id", sa.Integer(), sa.ForeignKey("answers.id", ondelete="RESTRICT")),
        sa.Column("parse_status", sa.String(32), nullable=False), sa.Column("confidence", sa.Numeric(6, 5)),
        sa.Column("raw_provider_response", sa.JSON()), sa.Column("reasoning_summary", sa.Text()), sa.Column("api_response_id", sa.String(255)),
        sa.Column("effective_model", sa.String(255)), sa.Column("latency_ms", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("criteria_scores", sa.JSON()), sa.Column("explanation", sa.Text()), sa.Column("provider_model", sa.String(255)), sa.Column("model_version", sa.String(255)),
        sa.UniqueConstraint("run_id", "pass_number", name="uq_pass_run_number"),
        sa.CheckConstraint("pass_number > 0", name="ck_pass_number_positive"),
        sa.CheckConstraint("presented_answer_a_id <> presented_answer_b_id", name="ck_pass_answers_distinct"),
        sa.CheckConstraint(PASS_VERDICTS, name="ck_pass_raw_verdict"), sa.CheckConstraint(PARSE_STATUSES, name="ck_pass_parse_status"),
        sa.CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ck_pass_confidence_range"),
        sa.CheckConstraint("latency_ms IS NULL OR latency_ms >= 0", name="ck_pass_latency_nonnegative"),
        sa.CheckConstraint("(raw_verdict = 'ANSWER_A' AND winner_answer_id = presented_answer_a_id) OR (raw_verdict = 'ANSWER_B' AND winner_answer_id = presented_answer_b_id) OR (raw_verdict IN ('TIE', 'UNKNOWN', 'ERROR') AND winner_answer_id IS NULL)", name="ck_pass_winner_mapping"),
    )
    op.create_index("ix_passes_raw_verdict", "passes", ["raw_verdict"])
    op.create_index("ix_passes_run_id", "passes", ["run_id"])


def downgrade() -> None:
    raise RuntimeError("Phase 1 recovery migrations are forward-only to protect research evidence.")
