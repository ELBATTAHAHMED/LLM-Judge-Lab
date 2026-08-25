"""Offline verifier template for the corrected source-text evidence package."""
from __future__ import annotations

import hashlib
import json
import sys
import uuid
from pathlib import Path


def root_from(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "backend").is_dir():
            return candidate
    raise RuntimeError("repository root not found")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


ROOT = root_from(Path(__file__).resolve().parent)
PACKAGE = ROOT / "evidence" / "final" / "controlled_source_text_corrected_v1"
manifest = json.loads((PACKAGE / "package_manifest.json").read_text(encoding="utf-8"))
inventory = manifest["file_inventory"]
assert all(sha256(PACKAGE / row["path"]) == row["sha256"] for row in inventory)
lines = "".join(row["sha256"] + "  " + row["path"] + "\n" for row in sorted(inventory, key=lambda row: row["path"]))
assert hashlib.sha256(lines.encode()).hexdigest() == manifest["package_root_digest"]
artifact = json.loads((PACKAGE / "source" / "source_corrected_complete_case_full_population_analysis_v2.json").read_text())
assert artifact["artifact_sha256"] == manifest["authoritative_analysis"]["artifact_sha256"]
sys.path.insert(0, str(ROOT / "backend"))
from database import SessionLocal  # noqa: E402
from controlled_models import AnalysisRun  # noqa: E402

with SessionLocal() as session:
    for _, row in json.loads((PACKAGE / "authoritative_analysis_runs.json").read_text()).items():
        current = session.get(AnalysisRun, uuid.UUID(row["id"]))
        assert current and current.result_json == row["result_json"]

print("CONTROLLED_SOURCE_TEXT_CORRECTED_PACKAGE_VERIFIED")
