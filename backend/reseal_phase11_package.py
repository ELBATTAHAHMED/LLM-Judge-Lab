"""Reseal Phase 11 control metadata after a verifier-only improvement.

Payload files are hashed deterministically.  The three control files remain
outside that payload hash scope to avoid circular hashing; this command never
touches database evidence or provider transports.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from freeze_final_evidence import PACKAGE, make_report, make_sums, secret_scan  # noqa: E402


def reseal() -> None:
    manifest_path = PACKAGE / "EVIDENCE_MANIFEST.json"
    metadata_path = PACKAGE / "PACKAGE_METADATA.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    inventory, root_digest = make_sums(PACKAGE)
    manifest["file_inventory"] = inventory
    manifest["package_root_digest"] = root_digest
    metadata["package_root_digest"] = root_digest
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    matches = secret_scan(PACKAGE)
    if matches:
        raise RuntimeError(f"secret marker(s) found in package: {matches}")
    make_report(PACKAGE, manifest, root_digest, manifest.get("database_snapshot"))


if __name__ == "__main__":
    reseal()
