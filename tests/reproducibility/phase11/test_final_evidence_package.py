"""Offline regression tests for the immutable Phase 11 evidence package."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "evidence" / "final" / "phase11"


def load(relative: str):
    return json.loads((PACKAGE / relative).read_text(encoding="utf-8"))


def test_phase11_offline_verifier_and_snapshot_are_valid():
    result = subprocess.run([sys.executable, str(PACKAGE / "VERIFY_PACKAGE.py")], cwd=PACKAGE, text=True, capture_output=True, check=True)
    assert result.stdout.strip().endswith("FINAL EVIDENCE PACKAGE VERIFIED")


def test_phase11_inventory_and_checksum_are_deterministic():
    manifest = load("EVIDENCE_MANIFEST.json")
    sums = (PACKAGE / "SHA256SUMS.txt").read_bytes()
    assert hashlib.sha256(sums).hexdigest() == manifest["package_root_digest"]
    assert len(manifest["file_inventory"]) >= 80
    for row in manifest["file_inventory"]:
        assert (PACKAGE / row["path"]).is_file()


def test_phase11_authoritative_accounting_and_isolation():
    manifest = load("EVIDENCE_MANIFEST.json")
    accounting = manifest["accounting"]
    assert (accounting["units"], accounting["planned_pass_slots"], accounting["valid_returned_passes"], accounting["failed_pass_slots"]) == (13_400, 16_600, 16_228, 372)
    units = load("evidence/units/controlled_units.json")
    science = load("evidence/runs/controlled_runs.json")
    superseded = load("audit_history/superseded_rq5/runs.json")
    pilot = load("audit_history/pilot/runs.json")
    assert len(units) == len({row["unit_id"] for row in units}) == 13_400
    assert len(science) == 13_400 and all(row["evidence_class"] == "CONTROLLED" for row in science)
    assert len(superseded) == 226 and all(row["evidence_class"] == "SUPERSEDED_CONTROLLED" for row in superseded)
    assert len(pilot) == 11 and all(row["evidence_class"] == "PILOT" for row in pilot)


def test_phase11_analysis_and_required_thesis_traceability_resolve():
    analysis = load("analysis/analysis_runs.json")
    traces = load("TRACEABILITY_INDEX.json")["metrics"]
    analysis_ids = {row["analysis_run_id"] for row in analysis}
    assert len(analysis) == 7 and {row["rq_code"] for row in analysis} == {f"RQ{i}" for i in range(1, 8)}
    assert all(row["analysis_run_id"] in analysis_ids for row in traces)
    required = {("RQ1", "exact_agreement"), ("RQ2", "consistency"), ("RQ3", "paired_decisive_flip_rate"), ("RQ4", "variant_win_rate"), ("RQ5", "variant_win_rate"), ("RQ6", "self_family_preference"), ("RQ7", "baseline_agreement"), ("RQ7", "dual_swap_agreement"), ("RQ7", "coverage_delta")}
    assert required <= {(row["rq_code"], row["metric_key"]) for row in traces}


def test_phase11_package_contains_no_configured_secret_markers():
    markers = ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "PGPASSWORD", "DATABASE_URL=", "Authorization: Bearer", "Bearer sk-")
    found = []
    for path in PACKAGE.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".png", ".dump"}:
            continue
        content = path.read_text(encoding="utf-8", errors="ignore").lower()
        if any(marker.lower() in content for marker in markers):
            found.append(path.relative_to(PACKAGE).as_posix())
    assert found == []
