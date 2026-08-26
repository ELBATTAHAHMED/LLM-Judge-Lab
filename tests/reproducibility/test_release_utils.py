"""Provider-free unit tests for shared release-tool helpers."""
from __future__ import annotations

import hashlib

from release_utils import postgres_connection, sha256


def test_release_helpers_hash_files_and_parse_postgres_urls_without_runtime_database_access(tmp_path):
    payload = tmp_path / "payload.bin"
    payload.write_bytes(b"release-utils")

    assert sha256(payload) == hashlib.sha256(b"release-utils").hexdigest()
    base, env = postgres_connection("postgresql+psycopg2://release_user:fixture_password@db.example:5433/judgelab")
    assert base == ["-h", "db.example", "-p", "5433", "-U", "release_user"]
    assert env["PGPASSWORD"] == "fixture_password"
