"""Shared provider-free PostgreSQL and hashing helpers for release tooling."""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit


PG_BIN = Path(os.environ.get("POSTGRES_BIN", r"C:\Program Files\PostgreSQL\17\bin"))


def sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file without loading it all into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def postgres_connection(database_url: str | None = None) -> tuple[list[str], dict[str, str]]:
    """Build safe PostgreSQL CLI connection arguments from the configured URL."""
    if database_url is None:
        from backend.core.database import DATABASE_URL

        database_url = DATABASE_URL
    parsed = urlsplit(database_url.replace("postgresql+psycopg2", "postgresql"))
    if parsed.scheme != "postgresql" or not parsed.hostname or not parsed.path:
        raise RuntimeError("A PostgreSQL DATABASE_URL is required for the physical release snapshot.")
    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = unquote(parsed.password)
    base = ["-h", parsed.hostname, "-p", str(parsed.port or 5432), "-U", unquote(parsed.username or "postgres")]
    return base, env


def run(command: list[str], *, env: dict[str, str]) -> str:
    """Run a PostgreSQL release-tool command and return its captured stdout."""
    completed = subprocess.run(command, check=True, text=True, capture_output=True, env=env)
    return completed.stdout
