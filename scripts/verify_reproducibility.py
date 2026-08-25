"""Verify canonical source data, frozen outputs, and optionally a fresh PostgreSQL build."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from canonical_source_data import compare_canonical_to_frozen_reconciliation, validate_canonical_source  # noqa: E402
from create_research_release_v2 import PG_BIN, postgres_connection, run  # noqa: E402
from database import DATABASE_URL  # noqa: E402


def temporary_url(name: str) -> str:
    parsed = urlsplit(DATABASE_URL.replace("postgresql+psycopg2", "postgresql"))
    if parsed.scheme != "postgresql" or not parsed.netloc:
        raise RuntimeError("A PostgreSQL DATABASE_URL is required for fresh-build verification.")
    return urlunsplit((parsed.scheme, parsed.netloc, f"/{name}", parsed.query, ""))


def fresh_empty_postgres_build() -> None:
    base, env = postgres_connection()
    psql = str(PG_BIN / "psql.exe")
    temporary = f"judgelab_canonical_{uuid.uuid4().hex[:12]}"
    created = False
    try:
        run([psql, *base, "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", f'CREATE DATABASE "{temporary}"'], env=env)
        created = True
        database_url = temporary_url(temporary)
        child_env = os.environ.copy()
        child_env["DATABASE_URL"] = database_url
        child_env["ALEMBIC_DATABASE_URL"] = database_url
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=child_env, check=True)
        subprocess.run([sys.executable, str(ROOT / "scripts" / "build_dataset.py")], cwd=ROOT, env=child_env, check=True)
        subprocess.run([sys.executable, str(ROOT / "scripts" / "run_evaluation.py"), "--limit", "2"], cwd=ROOT, env=child_env, check=True)
        code = "import sys;sys.path.insert(0,'backend');from database import SessionLocal;from canonical_source_data import verify_fresh_dataset; s=SessionLocal(); print(verify_fresh_dataset(s)); s.close()"
        subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=child_env, check=True)
    finally:
        if created:
            run([psql, *base, "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", f'DROP DATABASE IF EXISTS "{temporary}"'], env=env)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fresh-empty-db", action="store_true")
    args = parser.parse_args()
    payload, _ = validate_canonical_source()
    print(compare_canonical_to_frozen_reconciliation(payload))
    subprocess.run([sys.executable, str(ROOT / "scripts" / "run_analysis.py")], cwd=ROOT, check=True)
    if args.fresh_empty_db:
        fresh_empty_postgres_build()
    print(f"CANONICAL_REPRODUCIBILITY_VERIFIED {payload['canonical_dataset_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
