"""Add dataset-level provenance without rewriting legacy evidence."""
from alembic import op
import sqlalchemy as sa

revision = "0002_phase2_provenance"
down_revision = "0001_legacy_baseline"
branch_labels = None
depends_on = None


PROVENANCE = "provenance_status IN ('LEGACY_INCOMPLETE', 'COMPLETE', 'UNKNOWN')"


def upgrade() -> None:
    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("version", sa.String(128)),
        sa.Column("license_text", sa.Text()),
        sa.Column("source_uri", sa.Text()),
        sa.Column("source_checksum", sa.String(64)),
        sa.Column("checksum_algorithm", sa.String(32)),
        sa.Column("imported_at", sa.DateTime()),
        sa.Column("import_status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("imported_prompt_count", sa.Integer()),
        sa.Column("imported_answer_count", sa.Integer()),
        sa.Column("imported_annotation_count", sa.Integer()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("length(trim(source_name)) > 0", name="ck_dataset_source_name_not_blank"),
        sa.CheckConstraint("import_status IN ('PENDING', 'SUCCEEDED', 'FAILED', 'UNKNOWN')", name="ck_dataset_import_status"),
        sa.CheckConstraint("source_checksum IS NULL OR (checksum_algorithm = 'SHA-256' AND length(source_checksum) = 64)", name="ck_dataset_sha256_checksum"),
        sa.CheckConstraint("(imported_prompt_count IS NULL OR imported_prompt_count >= 0) AND (imported_answer_count IS NULL OR imported_answer_count >= 0) AND (imported_annotation_count IS NULL OR imported_annotation_count >= 0)", name="ck_dataset_row_counts_nonnegative"),
        sa.UniqueConstraint("source_name", "version", "source_checksum", name="uq_dataset_source_version_checksum"),
    )
    op.create_index("ix_dataset_versions_import_status", "dataset_versions", ["import_status"])
    op.create_index("ix_dataset_versions_source_name", "dataset_versions", ["source_name"])

    for table, extra_columns in {
        "prompts": [
            sa.Column("dataset_version_id", sa.Uuid(), nullable=True),
            sa.Column("source_record_id", sa.String(255), nullable=True),
            sa.Column("turn_id", sa.Integer(), nullable=True),
            sa.Column("provenance_status", sa.String(32), nullable=False, server_default="LEGACY_INCOMPLETE"),
        ],
        "answers": [
            sa.Column("dataset_version_id", sa.Uuid(), nullable=True),
            sa.Column("source_record_id", sa.String(255), nullable=True),
            sa.Column("turn_id", sa.Integer(), nullable=True),
            sa.Column("provenance_status", sa.String(32), nullable=False, server_default="LEGACY_INCOMPLETE"),
        ],
        "human_preferences": [
            sa.Column("dataset_version_id", sa.Uuid(), nullable=True),
            sa.Column("source_record_id", sa.String(255), nullable=True),
            sa.Column("annotator_id", sa.String(255), nullable=True),
            sa.Column("annotation_timestamp", sa.DateTime(), nullable=True),
            sa.Column("annotation_source", sa.String(100), nullable=True),
            sa.Column("adjudication_status", sa.String(64), nullable=True),
            sa.Column("provenance_status", sa.String(32), nullable=False, server_default="LEGACY_INCOMPLETE"),
        ],
    }.items():
        with op.batch_alter_table(table) as batch:
            for column in extra_columns:
                batch.add_column(column)
            batch.create_foreign_key(f"{table}_dataset_version_id_fkey", "dataset_versions", ["dataset_version_id"], ["id"], ondelete="SET NULL")
            batch.create_check_constraint(f"ck_{table}_provenance_status", PROVENANCE)
            if table != "human_preferences":
                batch.create_check_constraint(f"ck_{table}_turn_id_nonnegative", "turn_id IS NULL OR turn_id >= 0")
    for table in ("prompts", "answers", "human_preferences"):
        op.create_index(f"ix_{table}_source_record_id", table, ["source_record_id"])


def downgrade() -> None:
    # Deliberately unavailable: provenance was added without modifying legacy rows.
    raise RuntimeError("Phase 1 recovery migrations are forward-only to protect research evidence.")
