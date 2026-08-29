"""Shared provider-free PostgreSQL and hashing helpers for release tooling."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit


def postgres_binary(name: str) -> str:
    """Locate a PostgreSQL client executable without assuming a local version.

    ``POSTGRES_BIN`` remains an explicit override for a directory containing
    the client tools.  Otherwise PATH is authoritative; Windows installations
    are discovered only as a version-agnostic last resort.
    """
    executable = f"{name}.exe" if os.name == "nt" else name
    configured = os.environ.get("POSTGRES_BIN")
    if configured:
        candidate = Path(configured) / executable
        if candidate.is_file():
            return str(candidate)
        raise RuntimeError(
            f"POSTGRES_BIN does not contain {executable}: {Path(configured)}"
        )

    discovered = shutil.which(name) or shutil.which(executable)
    if discovered:
        return discovered

    if os.name == "nt":
        roots = {os.environ.get("ProgramW6432"), os.environ.get("ProgramFiles")}
        for root in filter(None, roots):
            postgres_root = Path(root) / "PostgreSQL"
            if not postgres_root.is_dir():
                continue
            for version_dir in sorted(postgres_root.iterdir(), reverse=True):
                candidate = version_dir / "bin" / executable
                if candidate.is_file():
                    return str(candidate)

    raise RuntimeError(
        f"Unable to locate PostgreSQL client executable {executable}. "
        "Set POSTGRES_BIN to its directory or add it to PATH."
    )


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
