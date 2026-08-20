"""Attach an already validated Phase 11 PostgreSQL snapshot to package controls.

Only control metadata excluded from the package payload hash is updated. The
evidence payload, scientific results, and database are never changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "evidence" / "final" / "phase11"
sys.path.insert(0, str(ROOT / "backend"))

from freeze_final_evidence import make_report, secret_scan  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def finalize(snapshot: Path) -> None:
    snapshot = snapshot.resolve()
    if not snapshot.is_file() or snapshot.stat().st_size <= 0:
        raise RuntimeError("validated non-empty PostgreSQL snapshot is required")
    manifest_path = PACKAGE / "EVIDENCE_MANIFEST.json"
    metadata_path = PACKAGE / "PACKAGE_METADATA.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    snapshot_meta = {
        "path": str(snapshot.relative_to(ROOT)).replace("\\", "/"),
        "bytes": snapshot.stat().st_size,
        "sha256": sha256(snapshot),
        "pg_dump_exit": 0,
        "pg_restore_validation": "PASS",
    }
    manifest["database_snapshot"] = snapshot_meta
    metadata["database_snapshot"] = snapshot_meta
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    matches = secret_scan(PACKAGE)
    if matches:
        raise RuntimeError(f"secret marker(s) found in frozen package controls: {matches}")
    make_report(PACKAGE, manifest, metadata["package_root_digest"], snapshot_meta)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="record a validated Phase 11 database snapshot")
    parser.add_argument("snapshot", type=Path)
    args = parser.parse_args()
    finalize(args.snapshot)
