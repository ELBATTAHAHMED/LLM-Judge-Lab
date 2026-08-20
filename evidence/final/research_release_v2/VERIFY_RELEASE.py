"""Offline verifier for the additive final-research-release-v2 package."""
from __future__ import annotations
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PG_RESTORE = Path(r"C:\Program Files\PostgreSQL\17\bin\pg_restore.exe")

def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()

def main() -> int:
    for line in (HERE / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        if digest(HERE / relative) != expected:
            raise SystemExit(f"checksum mismatch: {relative}")
    snapshot = HERE / "database" / "judgelab-final-research-release-v2.dump"
    if not PG_RESTORE.exists():
        raise SystemExit("pg_restore.exe unavailable for archive verification")
    subprocess.run([str(PG_RESTORE), "--list", str(snapshot)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, str(ROOT / "evidence" / "final" / "phase11" / "VERIFY_PACKAGE.py")], check=True)
    print("FINAL_RESEARCH_RELEASE_V2_VERIFIED")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
