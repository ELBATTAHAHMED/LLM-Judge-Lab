"""Provider-free unit tests for shared release-tool helpers."""
from __future__ import annotations

import hashlib

import pytest

from backend.release import utils
from backend.release.utils import postgres_binary, postgres_connection, sha256
from backend.release import verify_v4_api as verify_v4


def test_release_helpers_hash_files_and_parse_postgres_urls_without_runtime_database_access(tmp_path):
    payload = tmp_path / "payload.bin"
    payload.write_bytes(b"release-utils")

    assert sha256(payload) == hashlib.sha256(b"release-utils").hexdigest()
    base, env = postgres_connection("postgresql+psycopg2://release_user:fixture_password@db.example:5433/judgelab")
    assert base == ["-h", "db.example", "-p", "5433", "-U", "release_user"]
    assert env["PGPASSWORD"] == "fixture_password"


def test_postgres_binary_uses_path_before_platform_discovery(monkeypatch):
    monkeypatch.delenv("POSTGRES_BIN", raising=False)
    monkeypatch.setattr(utils.shutil, "which", lambda name: "/portable/bin/pg_restore" if name == "pg_restore" else None)

    assert postgres_binary("pg_restore") == "/portable/bin/pg_restore"


def test_postgres_binary_fails_with_actionable_message_when_unavailable(monkeypatch):
    monkeypatch.delenv("POSTGRES_BIN", raising=False)
    monkeypatch.setattr(utils.os, "name", "posix")
    monkeypatch.setattr(utils.shutil, "which", lambda _name: None)

    with pytest.raises(RuntimeError, match="Set POSTGRES_BIN.*PATH"):
        postgres_binary("pg_restore")


def test_release_v4_checks_run_against_the_explicit_restored_database(monkeypatch):
    calls: list[tuple[list[str], dict[str, str]]] = []

    def capture(command, **kwargs):
        calls.append((command, kwargs["env"]))

    monkeypatch.setattr(verify_v4.subprocess, "run", capture)
    restored_url = "postgresql://release_user:fixture_password@db.example:5433/judgelab_restored"

    verify_v4.api_check(restored_url)
    verify_v4.recompute_check(restored_url)

    assert len(calls) == 2
    assert all(env["DATABASE_URL"] == restored_url for _, env in calls)
    assert calls[0][0][:2] == [verify_v4.sys.executable, "-c"]
    assert calls[1][0][-1] == "--recompute-from-db"


def test_release_v4_stops_before_restore_when_dump_checksum_is_wrong(monkeypatch, tmp_path):
    bad_dump = tmp_path / "bad.dump"
    bad_dump.write_bytes(b"not the frozen release dump")
    monkeypatch.setattr(verify_v4, "SNAPSHOT", bad_dump)
    monkeypatch.setattr(verify_v4, "postgres_connection", lambda: (_ for _ in ()).throw(AssertionError("restore must not begin")))

    with pytest.raises(RuntimeError, match="dump checksum mismatch"):
        verify_v4.main()
