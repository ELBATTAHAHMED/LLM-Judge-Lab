"""Restore research-release v4 into a disposable database and validate its API.

This verifier is provider-free.  It never writes to the development database;
the temporary restored database is always dropped after the local API check.
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.release.utils import PG_BIN, postgres_connection, run, sha256

RELEASE = ROOT / "evidence" / "final" / "research_release_v4"
SNAPSHOT = RELEASE / "database" / "judgelab-research-release-v4.dump"


def restored_database_url(name: str) -> str:
    """Return the current PostgreSQL URL with only the database name replaced."""
    from backend.core.database import DATABASE_URL

    parsed = urlsplit(DATABASE_URL.replace("postgresql+psycopg2", "postgresql"))
    if parsed.scheme != "postgresql" or not parsed.netloc:
        raise RuntimeError("A PostgreSQL DATABASE_URL is required for release validation.")
    return urlunsplit((parsed.scheme, parsed.netloc, f"/{name}", parsed.query, ""))


def api_check(database_url: str) -> None:
    """Run the real route in a new process that can only see the restored DB."""
    code = r'''
import sys
sys.path.insert(0, "..")
import uuid
from fastapi.testclient import TestClient
from backend.core.controlled_models import AnalysisRun
from backend.core.database import SessionLocal
from backend.core.final_evidence import CANONICAL_FINAL_ANALYSIS_RUNS, CANONICAL_RQ7_SECONDARY_ANALYSIS_RUN
from main import app

response = TestClient(app).get("/api/controlled/results")
assert response.status_code == 200, response.text
payload = response.json()
assert payload["status"] == "CONTROLLED_RESULTS_AVAILABLE", payload
assert payload["analysis_runs"] == CANONICAL_FINAL_ANALYSIS_RUNS, payload["analysis_runs"]

with SessionLocal() as session:
    rows = {rq: session.get(AnalysisRun, uuid.UUID(run_id)) for rq, run_id in CANONICAL_FINAL_ANALYSIS_RUNS.items()}
    secondary = session.get(AnalysisRun, uuid.UUID(CANONICAL_RQ7_SECONDARY_ANALYSIS_RUN))
    assert all(rows.values()) and secondary is not None
    expected = {
        (rq, key): metric
        for rq, run in rows.items()
        for key, metric in run.result_json["metrics"].items()
    }
    actual = {(row["rq"], row["metric_key"]): row for row in payload["results"]}
    assert set(actual) == set(expected)
    for key, metric in expected.items():
        row = actual[key]
        assert row["value"] == metric["value"], key
        assert row["numerator"] == metric["numerator"], key
        assert row["denominator"] == metric["denominator"], key
        assert row["ci_low"] == metric["ci_low"], key
        assert row["ci_high"] == metric["ci_high"], key
    output = payload["secondary_mitigations"]["multi_judge_consensus"]
    metrics = secondary.result_json["metrics"]
    assert output["analysis_run_id"] == str(secondary.id)
    assert output["planned_n"] == metrics["planned_n"]
    assert output["retained_n"] == metrics["consensus_covered_n"]
    assert output["agreement"] == metrics["agreement"]
    assert output["coverage"] == metrics["coverage"]
    assert output["comparator_agreement"] == metrics["equal_weight_individual_comparator"]
    assert output["matched_delta"] == metrics["matched_delta"]
    assert output["ci_95"] == metrics["matched_delta_ci_95"]
    assert output["direct_dualswap_comparison"] == "NOT_DEFENSIBLE"
print("RESEARCH_RELEASE_V4_API_RECONCILIATION_VERIFIED")
'''
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    subprocess.run([sys.executable, "-c", code], cwd=ROOT / "backend", env=env, check=True)


def main() -> int:
    if sha256(SNAPSHOT) != "db138478cda7ebb1b560595378dad3b3e49f32ae99f4a2ff02c09cb359f4e254":
        raise RuntimeError("research_release_v4 dump checksum mismatch")
    base, env = postgres_connection()
    psql, restore = str(PG_BIN / "psql.exe"), str(PG_BIN / "pg_restore.exe")
    temporary = f"judgelab_v4_api_verify_{uuid.uuid4().hex[:12]}"
    created = False
    try:
        run([psql, *base, "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", f'CREATE DATABASE "{temporary}"'], env=env)
        created = True
        run([restore, "--no-owner", "--no-privileges", "--dbname", temporary, *base, str(SNAPSHOT)], env=env)
        api_check(restored_database_url(temporary))
    finally:
        if created:
            run([psql, *base, "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", f'DROP DATABASE IF EXISTS "{temporary}"'], env=env)
    print("RESEARCH_RELEASE_V4_FRESH_RESTORE_API_VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
