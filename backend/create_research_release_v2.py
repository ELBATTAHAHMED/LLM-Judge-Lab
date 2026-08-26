"""Create the additive, provider-free final research-release evidence package.

This never invokes a model provider and never touches Phase 11.  It creates a
new PostgreSQL custom-format snapshot, validates that archive with pg_restore,
and performs a disposable database restore/read test before writing checksums.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from controlled_models import AnalysisRun, DatasetVersion, ExperimentalUnit
from database import DATABASE_URL, SessionLocal
from final_evidence import CANONICAL_FINAL_ANALYSIS_RUNS, CANONICAL_FINAL_MANIFESTS
from release_utils import PG_BIN, postgres_connection, run, sha256


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "evidence" / "final" / "research_release_v2"
def verify_restore(snapshot: Path, *, base: list[str], env: dict[str, str]) -> dict[str, object]:
    """Restore only into a unique disposable database and remove it afterwards."""
    psql = str(PG_BIN / "psql.exe")
    restore = str(PG_BIN / "pg_restore.exe")
    temporary = f"judgelab_release_verify_{uuid.uuid4().hex[:12]}"
    created = False
    try:
        run([psql, *base, "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", f'CREATE DATABASE "{temporary}"'], env=env)
        created = True
        run([restore, "--no-owner", "--no-privileges", "--dbname", temporary, *base, str(snapshot)], env=env)
        output = run([psql, *base, "-d", temporary, "-At", "-v", "ON_ERROR_STOP=1", "-c", "SELECT count(*) FROM analysis_runs"], env=env).strip()
        return {"status": "PASSED", "restored_analysis_run_count": int(output)}
    finally:
        if created:
            run([psql, *base, "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", f'DROP DATABASE IF EXISTS "{temporary}"'], env=env)


def main() -> int:
    if not (PG_BIN / "pg_dump.exe").exists():
        raise RuntimeError(f"PostgreSQL client tools are unavailable at {PG_BIN}")
    RELEASE.mkdir(parents=True, exist_ok=True)
    database_dir = RELEASE / "database"; database_dir.mkdir(exist_ok=True)
    dataset_dir = RELEASE / "dataset"; dataset_dir.mkdir(exist_ok=True)
    base, env = postgres_connection()
    snapshot = database_dir / "judgelab-final-research-release-v2.dump"
    run([str(PG_BIN / "pg_dump.exe"), "--format=custom", "--no-owner", "--no-privileges", "--file", str(snapshot), *base, DATABASE_URL.rsplit("/", 1)[-1].split("?", 1)[0]], env=env)
    archive_list = database_dir / "pg_restore_list.txt"
    archive_list.write_text(run([str(PG_BIN / "pg_restore.exe"), "--list", str(snapshot)], env=env), encoding="utf-8")
    restore_check = verify_restore(snapshot, base=base, env=env)

    with SessionLocal() as session:
        dataset = session.get(DatasetVersion, "2f8c7bba-08b1-4d8b-8b0e-b564e8a61886")
        if dataset is None:
            raise RuntimeError("Expected DatasetVersion is missing")
        analyses = {rq: session.get(AnalysisRun, run_id) for rq, run_id in CANONICAL_FINAL_ANALYSIS_RUNS.items()}
        if any(row is None or row.status != "COMPLETED" for row in analyses.values()):
            raise RuntimeError("A pinned final AnalysisRun is missing or incomplete")
        source_prompt_ids = sorted({unit.prompt_id for unit in session.query(ExperimentalUnit).filter(ExperimentalUnit.manifest_id.in_(CANONICAL_FINAL_MANIFESTS.values())).all()})
        raw_names = ["question.jsonl", "human_judgment.jsonl", "alpaca-13b.jsonl", "claude-v1.jsonl", "gpt-3.5-turbo.jsonl", "gpt-4.jsonl", "llama-13b.jsonl", "vicuna-13b.jsonl"]
        dataset_export = {
            "scope": "Canonical raw source files used by the final controlled prompt subset; this does not claim the legacy whole-database DatasetVersion counts are the final experimental sample.",
            "prompt_ids": source_prompt_ids,
            "raw_files": [{"path": f"data/{name}", "sha256": sha256(ROOT / "data" / name)} for name in raw_names],
            "license_attribution_status": "UNVERIFIED_IN_LOCAL_SOURCE_METADATA",
        }
        dataset_export_path = dataset_dir / "canonical_controlled_source_manifest.json"
        dataset_export_path.write_text(json.dumps(dataset_export, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        manifest = {
            "release": "final-research-release-v2",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "provider_calls": 0,
            "phase11": {"path": "evidence/final/phase11", "root_digest": "f1a1d6ffcb6f6fd5a5dd48f7b51a731d6b765a68ff76501bf6c0ef356e53ce13", "immutable": True},
            "analysis_runs": {rq: {"id": str(row.id), "manifest_id": str(row.manifest_id), "analysis_version": row.analysis_version} for rq, row in analyses.items()},
            "dataset_reconciliation": {
                "legacy_dataset_version": {"id": str(dataset.id), "recorded_prompts": dataset.imported_prompt_count, "recorded_answers": dataset.imported_answer_count, "recorded_human_reference_pairs": dataset.imported_annotation_count},
                "canonical_controlled_source": {"raw_prompt_count": 80, "prompt_id_range": [min(source_prompt_ids), max(source_prompt_ids)], "controlled_prompt_count": len(source_prompt_ids), "export_manifest": "dataset/canonical_controlled_source_manifest.json"},
                "resolution": "The 107/2,139 DatasetVersion fields are legacy whole-database import metadata, not the final controlled source subset. Canonical controlled units use exactly the 80 raw prompts with IDs 81–160. Licensing and upstream attribution are unverified in the checked-in source metadata."
            },
            "rq6_addendum": {"path": "evidence/final/rq6_counterbalanced/provenance.json", "selection_manifest_sha256": "27ec2c49ee8129802bd924e96734b4efb03249e506e7fbd9968977575b42c5cc"},
            "database_snapshot": {"path": snapshot.relative_to(RELEASE).as_posix(), "sha256": sha256(snapshot), "pg_restore_list": archive_list.relative_to(RELEASE).as_posix(), "restore_test": restore_check},
        }
    (RELEASE / "RELEASE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    files = sorted(path for path in RELEASE.rglob("*") if path.is_file() and path.name not in {"SHA256SUMS.txt", "VERIFY_RELEASE.py"})
    (RELEASE / "SHA256SUMS.txt").write_text("".join(f"{sha256(path)}  {path.relative_to(RELEASE).as_posix()}\n" for path in files), encoding="utf-8")
    print(json.dumps({"release": str(RELEASE), "snapshot_sha256": manifest["database_snapshot"]["sha256"], "restore_test": restore_check}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
