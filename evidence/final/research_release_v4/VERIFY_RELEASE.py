"""Offline verifier template for research_release_v4."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


def root_from(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "backend").is_dir():
            return candidate
    raise RuntimeError("repository root not found")


ROOT = root_from(Path(__file__).resolve().parent)
RELEASE = ROOT / "evidence" / "final" / "research_release_v4"
for line in (RELEASE / "SHA256SUMS.txt").read_text().splitlines():
    digest, relative = line.split("  ", 1)
    assert hashlib.sha256((RELEASE / relative).read_bytes()).hexdigest() == digest
manifest = json.loads((RELEASE / "RELEASE_MANIFEST.json").read_text())
assert manifest["release"] == "research_release_v4"
assert len(manifest["authoritative_corrected_analysis"]["analysis_runs"]) == 8
subprocess.run([r"C:\Program Files\PostgreSQL\17\bin\pg_restore.exe", "--list", str(RELEASE / "database" / "judgelab-research-release-v4.dump")], check=True, stdout=subprocess.DEVNULL)
subprocess.run([sys.executable, str(ROOT / "evidence" / "final" / "controlled_source_text_corrected_v1" / "VERIFY_PACKAGE.py")], check=True)
print("RESEARCH_RELEASE_V4_VERIFIED")
