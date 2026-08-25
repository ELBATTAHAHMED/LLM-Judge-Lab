"""Create an additive provider-free v4 snapshot of corrected controlled science."""
from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from controlled_models import AnalysisRun
from create_research_release_v2 import PG_BIN, postgres_connection, run, sha256
from database import DATABASE_URL, SessionLocal
from final_evidence import CANONICAL_FINAL_ANALYSIS_RUNS, CANONICAL_RQ7_SECONDARY_ANALYSIS_RUN, CORRECTED_ANALYSIS_VERSION, CORRECTED_ARTIFACT_SHA256

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "evidence" / "final" / "research_release_v4"
CORRECTED = ROOT / "evidence" / "final" / "controlled_source_text_corrected_v1"


def restore(snapshot: Path, base: list[str], env: dict[str, str]) -> dict[str, object]:
    name = f"judgelab_v4_verify_{uuid.uuid4().hex[:10]}"
    psql, restore_bin = str(PG_BIN / "psql.exe"), str(PG_BIN / "pg_restore.exe")
    created = False
    try:
        run([psql, *base, "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", f'CREATE DATABASE "{name}"'], env=env); created = True
        run([restore_bin, "--no-owner", "--no-privileges", "--dbname", name, *base, str(snapshot)], env=env)
        query = lambda sql: run([psql, *base, "-d", name, "-At", "-v", "ON_ERROR_STOP=1", "-c", sql], env=env).strip()
        ids = [*CANONICAL_FINAL_ANALYSIS_RUNS.values(), CANONICAL_RQ7_SECONDARY_ANALYSIS_RUN]
        found = int(query("SELECT count(*) FROM analysis_runs WHERE id IN (" + ",".join("'" + value + "'" for value in ids) + ")"))
        return {"status": "PASSED", "authoritative_analysis_runs": found, "analysis_runs": int(query("SELECT count(*) FROM analysis_runs"))}
    finally:
        if created:
            run([psql, *base, "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", f'DROP DATABASE IF EXISTS "{name}"'], env=env)


def main() -> int:
    if not (PG_BIN / "pg_dump.exe").exists():
        raise RuntimeError("PostgreSQL client tools are unavailable")
    package = json.loads((CORRECTED / "package_manifest.json").read_text(encoding="utf-8"))
    if package["authoritative_analysis"]["artifact_sha256"] != CORRECTED_ARTIFACT_SHA256:
        raise RuntimeError("corrected package does not match the authoritative artifact")
    ids = {**CANONICAL_FINAL_ANALYSIS_RUNS, "RQ7_SECONDARY": CANONICAL_RQ7_SECONDARY_ANALYSIS_RUN}
    with SessionLocal() as session:
        rows = {key: session.get(AnalysisRun, uuid.UUID(value)) for key, value in ids.items()}
        if any(row is None or row.status != "COMPLETED" or row.analysis_version != CORRECTED_ANALYSIS_VERSION or (row.result_json or {}).get("artifact_sha256") != CORRECTED_ARTIFACT_SHA256 for row in rows.values()):
            raise RuntimeError("authoritative corrected AnalysisRun contract mismatch")
        total_runs = session.query(AnalysisRun).count()
    base, env = postgres_connection(); database = RELEASE / "database"; database.mkdir(parents=True, exist_ok=True)
    snapshot = database / "judgelab-research-release-v4.dump"
    run([str(PG_BIN / "pg_dump.exe"), "--format=custom", "--no-owner", "--no-privileges", "--file", str(snapshot), *base, DATABASE_URL.rsplit("/", 1)[-1].split("?", 1)[0]], env=env)
    listing = database / "pg_restore_list.txt"
    listing.write_text(run([str(PG_BIN / "pg_restore.exe"), "--list", str(snapshot)], env=env), encoding="utf-8")
    restored = restore(snapshot, base, env)
    if restored["status"] != "PASSED" or restored["authoritative_analysis_runs"] != len(ids):
        raise RuntimeError(f"release v4 restore validation mismatch: {restored}")
    manifest = {"release": "research_release_v4", "created_at": datetime.now(timezone.utc).isoformat(), "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "provider_calls": 0, "authoritative_corrected_analysis": {"artifact_sha256": CORRECTED_ARTIFACT_SHA256, "analysis_version": CORRECTED_ANALYSIS_VERSION, "analysis_runs": ids}, "corrected_evidence_package": {"path": "evidence/final/controlled_source_text_corrected_v1", "package_root_digest": package["package_root_digest"]}, "database_snapshot": {"path": "database/" + snapshot.name, "sha256": sha256(snapshot), "size_bytes": snapshot.stat().st_size, "pg_restore_list": "database/pg_restore_list.txt", "restore_validation": restored}, "historical_evidence_preserved": {"phase11": True, "research_release_v2": True, "research_release_v3": True, "multijudge_consensus_v1": True}, "analysis_runs_in_snapshot": total_runs}
    (RELEASE / "RELEASE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    files = sorted(path for path in RELEASE.rglob("*") if path.is_file() and path.name not in {"SHA256SUMS.txt", "VERIFY_RELEASE.py"})
    (RELEASE / "SHA256SUMS.txt").write_text("".join(f"{sha256(path)}  {path.relative_to(RELEASE).as_posix()}\n" for path in files), encoding="utf-8")
    shutil.copyfile(ROOT / "backend" / "verify_research_release_v4.py", RELEASE / "VERIFY_RELEASE.py")
    print(json.dumps({"release": str(RELEASE), "root_digest": sha256(RELEASE / "SHA256SUMS.txt"), "dump_sha256": manifest["database_snapshot"]["sha256"], "restore": restored}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
