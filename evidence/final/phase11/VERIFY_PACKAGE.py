#!/usr/bin/env python3
"""Offline Phase 11 evidence-package verifier; no provider or database access."""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTROL = {"EVIDENCE_MANIFEST.json", "PACKAGE_METADATA.json", "SHA256SUMS.txt"}
EXPECTED = {"dataset_id": "2f8c7bba-08b1-4d8b-8b0e-b564e8a61886", "dataset_sha": "b2fff1524b199fb2d302b7c4ebd752a9a47d32bab68a232ab06b7b1e07fa1510", "units": 13400, "planned_pass_slots": 16600, "valid_returned_passes": 16228, "failed_pass_slots": 372, "superseded_rq5": 226, "pilot": 11}
def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1048576),b""): h.update(b)
    return h.hexdigest()
def fail(msg): raise RuntimeError(msg)
def main():
    manifest=json.loads((ROOT/"EVIDENCE_MANIFEST.json").read_text(encoding="utf-8"))
    meta=json.loads((ROOT/"PACKAGE_METADATA.json").read_text(encoding="utf-8"))
    sums=(ROOT/"SHA256SUMS.txt").read_bytes()
    entries=[line.split("  ",1) for line in sums.decode("utf-8").splitlines() if line]
    if any(len(e)!=2 for e in entries): fail("malformed SHA256SUMS")
    if hashlib.sha256(sums).hexdigest()!=meta["package_root_digest"]: fail("root digest mismatch")
    for checksum, rel in entries:
        path=ROOT/rel
        if not path.is_file() or sha(path)!=checksum: fail(f"checksum mismatch: {rel}")
    if manifest["dataset"]["id"]!=EXPECTED["dataset_id"] or manifest["dataset"]["sha256"]!=EXPECTED["dataset_sha"]: fail("dataset identity mismatch")
    snapshot=manifest.get("database_snapshot")
    if not snapshot: fail("missing database snapshot metadata")
    snapshot_path=ROOT.parents[2]/snapshot["path"]
    if not snapshot_path.is_file() or snapshot_path.stat().st_size!=snapshot["bytes"] or sha(snapshot_path)!=snapshot["sha256"]: fail("database snapshot mismatch")
    counts=manifest["accounting"]
    for key in ("units","planned_pass_slots","valid_returned_passes","failed_pass_slots","superseded_rq5","pilot"):
        if counts[key]!=EXPECTED[key]: fail(f"accounting mismatch: {key}")
    analysis=json.loads((ROOT/"analysis"/"analysis_runs.json").read_text(encoding="utf-8"))
    if len(analysis)!=7 or {r["rq_code"] for r in analysis}!={f"RQ{i}" for i in range(1,8)}: fail("AnalysisRun set mismatch")
    units=json.loads((ROOT/"evidence"/"units"/"controlled_units.json").read_text(encoding="utf-8"))
    if len(units)!=EXPECTED["units"] or len({r["unit_id"] for r in units})!=len(units): fail("unit index mismatch")
    manifests=[json.loads((ROOT/"manifests"/f"rq{i}_manifest.json").read_text(encoding="utf-8")) for i in range(1,8)]
    if len({r["manifest_id"] for r in manifests})!=7: fail("manifest identity mismatch")
    trace=json.loads((ROOT/"TRACEABILITY_INDEX.json").read_text(encoding="utf-8"))
    ids={r["analysis_run_id"] for r in analysis}
    if any(r["analysis_run_id"] not in ids for r in trace["metrics"]): fail("broken trace AnalysisRun reference")
    runs=json.loads((ROOT/"evidence"/"runs"/"controlled_runs.json").read_text(encoding="utf-8"))
    if len(runs)!=EXPECTED["units"] or len({r["run_id"] for r in runs})!=len(runs) or any(r["evidence_class"]!="CONTROLLED" for r in runs): fail("controlled run isolation/identity mismatch")
    if counts.get("pending")!=0: fail("pending provider-eligible unit present")
    for relative, key in (("evidence/passes/controlled_passes.json", "pass_id"), ("evidence/attempts/controlled_attempts.json", "attempt_row_id")):
        rows=json.loads((ROOT/relative).read_text(encoding="utf-8"))
        if len({r[key] for r in rows})!=len(rows): fail(f"duplicate {key}")
    if len(json.loads((ROOT/"audit_history"/"superseded_rq5"/"runs.json").read_text(encoding="utf-8")))!=EXPECTED["superseded_rq5"]: fail("superseded RQ5 isolation mismatch")
    if len(json.loads((ROOT/"audit_history"/"pilot"/"runs.json").read_text(encoding="utf-8")))!=EXPECTED["pilot"]: fail("pilot isolation mismatch")
    print("FINAL EVIDENCE PACKAGE VERIFIED")
if __name__ == "__main__":
    main()
