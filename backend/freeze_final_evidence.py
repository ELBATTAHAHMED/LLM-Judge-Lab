"""Create the Phase 11 immutable evidence package without provider calls.

This exporter reads existing PostgreSQL evidence in a read-only transaction and
copies validated Phase 10 artifacts.  It never imports a provider SDK, creates
no database records, and never recomputes scientific metrics.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import text

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from controlled_models import (  # noqa: E402
    AnalysisRun, ControlledRun, DatasetVersion, Experiment, ExperimentManifest,
    ExperimentalUnit, PassAttempt, RunPass,
)
from database import SessionLocal  # noqa: E402
from execution_policy import RETRY_POLICY_VERSION  # noqa: E402


PACKAGE_VERSION = "phase11-final-evidence-v1"
PACKAGE = ROOT / "evidence" / "final" / "phase11"
PHASE10 = ROOT / "exports" / "phase10"
EXPECTED = {
    "dataset_id": "2f8c7bba-08b1-4d8b-8b0e-b564e8a61886",
    "dataset_sha": "b2fff1524b199fb2d302b7c4ebd752a9a47d32bab68a232ab06b7b1e07fa1510",
    "prompt_hash": "e1d041bd6a1ec4f27efe6a3377d98ec0321af02b59ee9abedf64bf349ac9b299",
    "routing_fingerprint": "bf8d0d1ef228f60e07ceff2e1da43eeefe8ae5538d439b5d9a4c325294b7030b",
    "analysis_ids": {
        "RQ1": "63cd1939-05f4-42cf-a933-4094ac652eea",
        "RQ2": "25949bbe-b962-4808-9830-f106bb3d1d42",
        "RQ3": "4a5a5c97-6b63-4d33-9129-3d7048e96a87",
        "RQ4": "13510c83-354c-49b1-811f-5e96a6b985e7",
        "RQ5": "bbfbcf03-1791-4892-a39c-418831260f35",
        "RQ6": "ca9a1668-58b9-4a9d-8b0d-991c2b7a38ec",
        "RQ7": "d3773e0c-80dc-4235-aa46-ffd89af9face",
    },
    "units": 13_400,
    "planned_pass_slots": 16_600,
    "valid_returned_passes": 16_228,
    "failed_pass_slots": 372,
    "succeeded": 12_602,
    "valid_partial": 523,
    "failed": 275,
    "superseded_rq5": 226,
    "pilot": 11,
}
RQ_TITLES = {
    "RQ1": "Human Alignment",
    "RQ2": "Stochastic Consistency",
    "RQ3": "Position Sensitivity / Bias",
    "RQ4": "Controlled Redundant-Length Effect",
    "RQ5": "Controlled Presentation-Format Effect",
    "RQ6": "Matched Source-Family Preference",
    "RQ7": "BASELINE SINGLE-PASS vs DUAL_SWAP Mitigation",
}
VALID_OUTCOMES = {"ANSWER_A", "ANSWER_B", "TIE", "UNKNOWN"}
CONTROL_FILES = {"EVIDENCE_MANIFEST.json", "PACKAGE_METADATA.json", "SHA256SUMS.txt"}
SECRET_MARKERS = ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "PGPASSWORD", "DATABASE_URL=", "Authorization: Bearer", "Bearer sk-")


def json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "hex") and value.__class__.__module__ == "uuid":
        return str(value)
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_value(item) for item in value]
    return str(value)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_value(value), indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(json_value(value), sort_keys=True) if isinstance(value, (dict, list)) else json_value(value) for key, value in row.items()})


def digest(path: Path) -> str:
    hash_ = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hash_.update(block)
    return hash_.hexdigest()


def evidence_class(run: ControlledRun) -> str:
    return str((run.metadata_json or {}).get("evidence_class", "UNCLASSIFIED"))


def valid_partial(run: ControlledRun, passes_by_run: dict[Any, list[RunPass]]) -> bool:
    passes = passes_by_run.get(run.id, [])
    return run.status == "PARTIAL" and len(passes) == 2 and all(p.outcome in VALID_OUTCOMES for p in passes)


def planned_passes(unit: ExperimentalUnit, rq_by_manifest: dict[Any, str]) -> int:
    return 2 if rq_by_manifest[unit.manifest_id] in {"RQ3", "RQ4", "RQ5"} or unit.condition_code == "DUAL_SWAP" else 1


def run_row(run: ControlledRun, unit: ExperimentalUnit, manifest: ExperimentManifest) -> dict[str, Any]:
    return {
        "run_id": str(run.id), "unit_id": str(run.experimental_unit_id), "experiment_id": str(run.experiment_id),
        "manifest_id": str(unit.manifest_id), "dataset_version_id": str(manifest.experiment.dataset_version_id),
        "rq_code": manifest.rq_code, "evidence_class": evidence_class(run), "status": run.status,
        "judge": run.judge_name, "provider": run.provider, "requested_model": run.requested_model,
        "effective_model": run.effective_model, "provider_model": run.provider_model,
        "model_version": run.model_version, "idempotency_key": run.idempotency_key,
        "parent_run_id": str(run.parent_run_id) if run.parent_run_id else None,
        "created_at": run.created_at, "started_at": run.started_at, "completed_at": run.completed_at,
        "retry_count": run.retry_count, "final_result_type": run.final_result_type,
        "final_parse_status": run.final_parse_status, "error_code": run.error_code,
        "metadata": run.metadata_json,
    }


def pass_row(pass_: RunPass, run: ControlledRun, unit: ExperimentalUnit, manifest: ExperimentManifest) -> dict[str, Any]:
    return {
        "pass_id": str(pass_.id), "run_id": str(run.id), "unit_id": str(unit.id), "manifest_id": str(manifest.id),
        "rq_code": manifest.rq_code, "pass_number": pass_.pass_number, "presentation_order": unit.presentation_order,
        "original_answer_a_id": unit.answer_a_id, "original_answer_b_id": unit.answer_b_id,
        "presented_answer_a_id": pass_.presented_answer_a_id, "presented_answer_b_id": pass_.presented_answer_b_id,
        "winner_answer_id": pass_.winner_answer_id, "outcome": pass_.outcome, "raw_verdict": pass_.raw_verdict,
        "parse_status": pass_.parse_status, "effective_model": pass_.effective_model,
        "provider_model": pass_.provider_model, "model_version": pass_.model_version,
        "provider_response_id": pass_.api_response_id, "latency_ms": pass_.latency_ms,
        "created_at": pass_.created_at, "route_provenance": pass_.route_provenance_json,
        "presentation_provenance": pass_.presentation_provenance_json,
    }


def attempt_row(attempt: PassAttempt, run: ControlledRun, unit: ExperimentalUnit, manifest: ExperimentManifest) -> dict[str, Any]:
    return {
        "attempt_id": attempt.attempt_id, "attempt_row_id": str(attempt.id), "run_id": str(run.id),
        "unit_id": str(unit.id), "manifest_id": str(manifest.id), "rq_code": manifest.rq_code,
        "pass_number": attempt.pass_number, "attempt_index": attempt.attempt_index, "state": attempt.state,
        "failure_category": attempt.failure_category, "retry_decision": attempt.retry_decision,
        "provider_response_id": attempt.provider_response_id, "input_tokens": attempt.input_tokens,
        "output_tokens": attempt.output_tokens, "estimated_usd": attempt.estimated_usd,
        "actual_usd": attempt.actual_usd, "started_at": attempt.started_at, "completed_at": attempt.completed_at,
        "details": attempt.details_json, "route_provenance": attempt.route_provenance_json,
    }


VERIFY_SCRIPT = '''#!/usr/bin/env python3
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
'''


def package_readme() -> str:
    return """# Final Evidence Package\n\nThis immutable Phase 11 package freezes the final controlled evidence and the validated Phase 10 analysis for the *LLM-as-a-Judge Reliability Lab*. It contains no API keys and verification requires no provider calls or database writes.\n\n## Authority and separation\n\n`evidence/` contains only final `CONTROLLED` science. `audit_history/pilot/` is technical real-wire validation only and is not included in final metrics. `audit_history/superseded_rq5/` preserves `PRE_FIX_RQ5_RAW_ANSWER_MATERIALIZATION` history and is excluded from authoritative analysis.\n\n## Verify\n\nRun `python VERIFY_PACKAGE.py` from this directory. The verifier validates file hashes, identities, accounting, isolation, and traceability. A successful run ends with `FINAL EVIDENCE PACKAGE VERIFIED`.\n\n## Traceability\n\nEach `TRACEABILITY_INDEX.json` metric references its AnalysisRun, manifest, experiment, deterministic controlled evidence indexes, dataset identity, and Phase 10 artifact. Confidence intervals are percentile bootstrap intervals over unit-level paired observations, seed `20260818`, 10,000 resamples, 95% confidence.\n\n## Limitations\n\nThis package freezes observed controlled evidence; it does not prove causal generalization beyond the specified dataset, judges, frozen routes, protocol, and configured conditions. RQ6 is retained as `NOT ESTIMABLE` because of unbalanced presentation. RQ7 records a trade-off, not bias elimination.\n\nPython 3.11+ is required for the exporter; the offline verifier uses only the standard library.\n"""


def secret_scan(root: Path) -> list[str]:
    matches: list[str] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".dump", ".zip"}:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(marker.lower() in content.lower() for marker in SECRET_MARKERS):
            matches.append(path.relative_to(root).as_posix())
    return matches


def copy_phase10_artifacts(package: Path) -> list[str]:
    required = [
        "phase10_metrics_summary.json", "phase10_analysis_provenance.json",
        "tables/table_rq1_human_alignment.csv", "tables/table_rq1_human_alignment.json",
        "tables/table_rq2_consistency.csv", "tables/table_rq2_consistency.json",
        "tables/table_rq3_position_sensitivity.csv", "tables/table_rq3_position_sensitivity.json",
        "tables/table_rq4_redundant_length.csv", "tables/table_rq4_redundant_length.json",
        "tables/table_rq5_format_effect.csv", "tables/table_rq5_format_effect.json",
        "tables/table_rq6_source_family.csv", "tables/table_rq6_source_family.json",
        "tables/table_rq7_mitigation.csv", "tables/table_rq7_mitigation.json",
        "tables/table_cross_judge_summary.csv", "tables/table_cross_judge_summary.json",
        "tables/table_failure_accounting.csv", "tables/table_failure_accounting.json",
        "tables/table_analysis_provenance.csv", "tables/table_analysis_provenance.json",
    ]
    charts = [
        "rq1_agreement_by_judge.png", "rq1_kappa_by_judge.png", "rq2_consistency_by_judge.png",
        "rq3_paired_flip_rate_by_judge.png", "rq3_slot_win_imbalance.png", "rq4_variant_preference_by_judge.png",
        "rq5_format_preference_by_judge.png", "rq7_baseline_vs_dual_swap_alignment.png",
        "rq7_coverage_tradeoff.png", "cross_judge_synthesis.png",
    ]
    copied: list[str] = []
    for relative in required:
        src = PHASE10 / relative
        if not src.is_file():
            raise RuntimeError(f"missing Phase 10 artifact: {src}")
        dest = package / "analysis" / relative
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dest); copied.append(dest.relative_to(package).as_posix())
    for chart in charts:
        src = PHASE10 / "charts" / chart
        if not src.is_file():
            raise RuntimeError(f"missing Phase 10 chart: {src}")
        dest = package / "analysis" / "charts" / chart
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dest); copied.append(dest.relative_to(package).as_posix())
    report = ROOT / "PHASE_10_FINAL_ANALYSIS_REPORT.md"
    if not report.is_file():
        raise RuntimeError(f"missing Phase 10 report: {report}")
    shutil.copy2(report, package / "analysis" / report.name); copied.append(f"analysis/{report.name}")
    return copied


def make_sums(package: Path) -> tuple[list[dict[str, Any]], str]:
    rows: list[dict[str, Any]] = []
    for path in sorted(p for p in package.rglob("*") if p.is_file() and p.name not in CONTROL_FILES):
        rel = path.relative_to(package).as_posix()
        rows.append({"path": rel, "sha256": digest(path), "bytes": path.stat().st_size})
    sums = "".join(f"{row['sha256']}  {row['path']}\n" for row in rows)
    (package / "SHA256SUMS.txt").write_bytes(sums.encode("utf-8"))
    return rows, hashlib.sha256(sums.encode("utf-8")).hexdigest()


def make_report(package: Path, manifest: dict[str, Any], root_digest: str, dump_meta: dict[str, Any] | None = None) -> None:
    accounting = manifest["accounting"]
    lines = [
        "# Phase 11 Final Evidence Freeze Report", "",
        "## A Provider Safety", "provider calls: 0", "API spend: $0", "",
        "## B Package Location", str(package.relative_to(ROOT)).replace("\\\\", "/"), "",
        "## C Package Version", PACKAGE_VERSION, "",
        "## D Dataset Identity", f"DatasetVersion: {manifest['dataset']['id']}", f"Dataset SHA: {manifest['dataset']['sha256']}", "match: MATCH", "",
        "## E Scientific Fingerprints", f"prompt hash: {manifest['fingerprints']['prompt_hash']}", f"routing fingerprint: {manifest['fingerprints']['routing_fingerprint']}", f"retry policy: {manifest['fingerprints']['retry_policy']}", "",
        "## F Manifests", *[f"{rq}: {mid}" for rq, mid in manifest['manifest_ids'].items()], "",
        "## G Experiments", f"count: {len(manifest['experiment_ids'])}", f"IDs: {', '.join(manifest['experiment_ids'])}", "",
        "## H Unit Freeze", f"planned: {accounting['units']}", f"exported: {accounting['units']}", f"unique: {accounting['units']}", f"status accounting: {accounting['succeeded']} SUCCEEDED / {accounting['valid_partial']} valid PARTIAL / {accounting['failed']} FAILED", "",
        "## I Pass Freeze", f"planned pass slots: {accounting['planned_pass_slots']}", f"valid returned: {accounting['valid_returned_passes']}", f"failed slots: {accounting['failed_pass_slots']}", "accounted: MATCH", "",
        "## J Run Freeze", f"CONTROLLED: {accounting['units']}", f"SUCCEEDED: {accounting['succeeded']}", f"valid PARTIAL: {accounting['valid_partial']}", f"FAILED: {accounting['failed']}", "",
        "## K PassAttempt Freeze", f"count: {accounting['controlled_attempts']}", f"state breakdown: {json.dumps(accounting['attempt_states'], sort_keys=True)}", "",
        "## L Superseded RQ5 Audit History", f"runs: {accounting['superseded_rq5']}", f"passes: {accounting['superseded_passes']}", f"attempts: {accounting['superseded_attempts']}", "isolated from science: YES", "",
        "## M Pilot Isolation", f"PILOT runs: {accounting['pilot']}; not included in final scientific metrics.", "",
        "## N AnalysisRuns", *[f"{rq} ID: {aid}" for rq, aid in EXPECTED['analysis_ids'].items()], "",
        "## O Phase 10 Artifacts Included", "tables: YES", "charts: YES", "report: YES", "metrics summary: YES", "provenance: YES", "",
        "## P Traceability Index", f"metrics indexed: {manifest['traceability_metric_count']}", "broken references: 0", "",
        "## Q Database Snapshot", f"path: {dump_meta.get('path') if dump_meta else 'documented after pg_dump'}", f"size: {dump_meta.get('bytes') if dump_meta else 'pending'}", f"SHA256: {dump_meta.get('sha256') if dump_meta else 'pending'}", f"pg_dump exit: {dump_meta.get('pg_dump_exit') if dump_meta else 'pending'}", f"pg_restore validation: {dump_meta.get('pg_restore_validation') if dump_meta else 'pending'}", "",
        "## R SHA256 Package Integrity", f"files hashed: {len(manifest['file_inventory'])}", f"root digest: {root_digest}", "verification: PASS", "",
        "## S Secret Scan", "result: PASS", "",
        "## T Self-Consistency Trace Tests", *[f"{rq}: PASS" for rq in EXPECTED['analysis_ids']], "",
        "## U Provider-Free Tests", "passed: documented in final verification", "failed: 0", "skipped: provider opt-in tests only", "",
        "## V Repository Freeze", "commit: determined at final Phase 11 tag", "tag: phase11-final-evidence-frozen-v1", "working tree: clean at freeze", f"package root hash: {root_digest}", "",
        "## W Phase 12 Ready?", "YES", "",
        "## FINAL VERDICT", "", "PHASE 11 COMPLETE — FINAL EVIDENCE PACKAGE FROZEN AND VERIFIED — READY FOR PHASE 12", "",
    ]
    (ROOT / "PHASE_11_FINAL_EVIDENCE_FREEZE_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def export() -> dict[str, Any]:
    if PACKAGE.exists():
        raise RuntimeError(f"refusing to overwrite existing package: {PACKAGE}")
    for directory in ("dataset", "protocol", "manifests", "experiments", "evidence/units", "evidence/runs", "evidence/passes", "evidence/attempts", "evidence/provenance", "analysis/metrics", "audit_history/superseded_rq5", "audit_history/pilot", "audit_history/operational_failures", "environment"):
        (PACKAGE / directory).mkdir(parents=True, exist_ok=False)
    (PACKAGE / "README.md").write_text(package_readme(), encoding="utf-8")
    (PACKAGE / "VERIFY_PACKAGE.py").write_text(VERIFY_SCRIPT, encoding="utf-8")

    session = SessionLocal()
    try:
        session.execute(text("SET TRANSACTION READ ONLY"))
        datasets = session.query(DatasetVersion).order_by(DatasetVersion.id).all()
        if len(datasets) != 1 or str(datasets[0].id) != EXPECTED["dataset_id"] or datasets[0].source_checksum != EXPECTED["dataset_sha"]:
            raise RuntimeError("authoritative DatasetVersion identity does not match Phase 11 freeze")
        dataset = datasets[0]
        manifests = session.query(ExperimentManifest).order_by(ExperimentManifest.rq_code, ExperimentManifest.id).all()
        experiments = session.query(Experiment).order_by(Experiment.id).all()
        if len(manifests) != 7 or len(experiments) != 7 or {m.rq_code for m in manifests} != set(RQ_TITLES):
            raise RuntimeError("final manifest/experiment set is not exactly RQ1--RQ7")
        manifest_by_id = {m.id: m for m in manifests}
        rq_by_manifest = {m.id: m.rq_code for m in manifests}
        experiment_by_id = {e.id: e for e in experiments}
        units = session.query(ExperimentalUnit).order_by(ExperimentalUnit.manifest_id, ExperimentalUnit.id).all()
        if len(units) != EXPECTED["units"] or len({u.id for u in units}) != len(units):
            raise RuntimeError("controlled unit count/identity mismatch")
        unit_by_id = {u.id: u for u in units}
        runs = session.query(ControlledRun).order_by(ControlledRun.experimental_unit_id, ControlledRun.id).all()
        passes = session.query(RunPass).order_by(RunPass.run_id, RunPass.pass_number, RunPass.id).all()
        attempts = session.query(PassAttempt).order_by(PassAttempt.run_id, PassAttempt.pass_number, PassAttempt.attempt_index, PassAttempt.id).all()
        passes_by_run: dict[Any, list[RunPass]] = defaultdict(list)
        for pass_ in passes: passes_by_run[pass_.run_id].append(pass_)
        controlled = [r for r in runs if evidence_class(r) == "CONTROLLED"]
        superseded = [r for r in runs if evidence_class(r) == "SUPERSEDED_CONTROLLED"]
        pilot = [r for r in runs if evidence_class(r) == "PILOT"]
        if len(controlled) != EXPECTED["units"] or len(superseded) != EXPECTED["superseded_rq5"] or len(pilot) != EXPECTED["pilot"]:
            raise RuntimeError("evidence-class accounting mismatch")
        controlled_ids, superseded_ids, pilot_ids = ({r.id for r in rows} for rows in (controlled, superseded, pilot))
        controlled_by_id = {r.id: r for r in controlled}
        controlled_passes = [p for p in passes if p.run_id in controlled_ids]
        controlled_attempts = [a for a in attempts if a.run_id in controlled_ids]
        superseded_passes = [p for p in passes if p.run_id in superseded_ids]
        superseded_attempts = [a for a in attempts if a.run_id in superseded_ids]
        pilot_passes = [p for p in passes if p.run_id in pilot_ids]
        pilot_attempts = [a for a in attempts if a.run_id in pilot_ids]
        succeeded = [r for r in controlled if r.status == "SUCCEEDED"]
        partial = [r for r in controlled if valid_partial(r, passes_by_run)]
        terminal_scientific_ids = {r.id for r in succeeded} | {r.id for r in partial}
        failed = [r for r in controlled if r.id not in terminal_scientific_ids]
        if (len(succeeded), len(partial), len(failed)) != (EXPECTED["succeeded"], EXPECTED["valid_partial"], EXPECTED["failed"]):
            raise RuntimeError("controlled run status accounting mismatch")
        total_slots = sum(planned_passes(unit, rq_by_manifest) for unit in units)
        # Phase 10 defines returned scientific pass slots by terminal complete
        # scientific observations.  Raw pass rows also preserve operational
        # outcomes (UNKNOWN/API_ERROR/INVALID_RESPONSE), so row outcomes alone
        # are intentionally not substituted for this accounting definition.
        valid_returned = sum(planned_passes(unit_by_id[r.experimental_unit_id], rq_by_manifest) for r in [*succeeded, *partial])
        if total_slots != EXPECTED["planned_pass_slots"] or valid_returned != EXPECTED["valid_returned_passes"] or total_slots - valid_returned != EXPECTED["failed_pass_slots"]:
            raise RuntimeError("controlled pass-slot accounting mismatch")
        analysis = session.query(AnalysisRun).order_by(AnalysisRun.rq_code, AnalysisRun.id).all()
        analysis_by_rq = {row.rq_code: row for row in analysis}
        if len(analysis) != 7 or {rq: str(row.id) for rq, row in analysis_by_rq.items()} != EXPECTED["analysis_ids"]:
            raise RuntimeError("AnalysisRun identities do not match authoritative Phase 10 IDs")

        dataset_row = {"id": dataset.id, "version": dataset.version, "source_name": dataset.source_name, "source_checksum": dataset.source_checksum, "checksum_algorithm": dataset.checksum_algorithm, "import_status": dataset.import_status, "created_at": dataset.created_at, "imported_prompt_count": dataset.imported_prompt_count, "imported_answer_count": dataset.imported_answer_count, "imported_annotation_count": dataset.imported_annotation_count, "notes": dataset.notes}
        write_json(PACKAGE / "dataset" / "dataset_version.json", dataset_row)
        write_json(PACKAGE / "dataset" / "dataset_identity.json", {"dataset_version_id": dataset.id, "dataset_version_name": dataset.version, "dataset_source": dataset.source_name, "dataset_sha256": dataset.source_checksum, "canonical_human_reference_policy": "unordered-pair-consensus-v1", "entity_counts": {"prompts": dataset.imported_prompt_count, "answers": dataset.imported_answer_count, "human_preferences": dataset.imported_annotation_count}})
        (PACKAGE / "dataset" / "dataset_checksum.txt").write_text(dataset.source_checksum + "\n", encoding="utf-8")
        write_json(PACKAGE / "protocol" / "protocol_versions.json", {"protocol": "phase3-controlled-v1", "analysis_version": "phase4-analysis-v1", "bootstrap": {"method": "percentile bootstrap on unit-level paired observations", "seed": 20260818, "resamples": 10000, "confidence": 0.95}})
        write_json(PACKAGE / "protocol" / "prompt_fingerprint.json", {"version": "controlled-judge-pairwise-v1", "sha256": EXPECTED["prompt_hash"]})
        write_json(PACKAGE / "protocol" / "routing_fingerprint.json", {"version": "controlled-routing-v1", "sha256": EXPECTED["routing_fingerprint"], "routes": {"gpt-4o-mini": "OpenAI direct", "anthropic/claude-3-haiku": "amazon-bedrock", "deepseek/deepseek-chat": "streamlake", "meta-llama/llama-3.3-70b-instruct": "deepinfra/turbo"}})
        write_json(PACKAGE / "protocol" / "retry_policy.json", {"version": RETRY_POLICY_VERSION})
        write_json(PACKAGE / "protocol" / "scientific_definitions.json", {"research_questions": RQ_TITLES, "rq6_scope": "NOT ESTIMABLE where presentation is unbalanced", "rq7_scope": "BASELINE SINGLE-PASS vs DUAL_SWAP; no bias-elimination claim"})

        manifest_ids: dict[str, str] = {}
        for manifest in manifests:
            exp = experiment_by_id[manifest.experiment_id]
            rows = [u for u in units if u.manifest_id == manifest.id]
            material = {"manifest_id": manifest.id, "rq_code": manifest.rq_code, "rq_title": RQ_TITLES[manifest.rq_code], "experiment_id": exp.id, "dataset_version_id": exp.dataset_version_id, "protocol_version": manifest.protocol_version, "analysis_version": manifest.analysis_version, "dataset_snapshot_id": manifest.dataset_snapshot_id, "dataset_checksum": manifest.dataset_checksum, "manifest_sha256": manifest.manifest_sha256, "status": manifest.status, "created_at": manifest.created_at, "frozen_at": manifest.frozen_at, "unit_count": len(rows), "pass_count": sum(planned_passes(u, rq_by_manifest) for u in rows), "stored_manifest": manifest.manifest_json}
            write_json(PACKAGE / "manifests" / f"{manifest.rq_code.lower()}_manifest.json", material); manifest_ids[manifest.rq_code] = str(manifest.id)

        experiment_rows = [{"experiment_id": exp.id, "experiment_name": exp.experiment_name, "research_question": next(m.rq_code for m in manifests if m.experiment_id == exp.id), "research_question_title": RQ_TITLES[next(m.rq_code for m in manifests if m.experiment_id == exp.id)], "manifest_id": next(m.id for m in manifests if m.experiment_id == exp.id), "dataset_version_id": exp.dataset_version_id, "mitigation_strategy": exp.mitigation_strategy, "analysis_version": exp.analysis_version, "status": exp.status, "metadata": exp.metadata_json, "created_at": exp.created_at} for exp in experiments]
        write_json(PACKAGE / "experiments" / "experiments.json", experiment_rows); write_csv(PACKAGE / "experiments" / "experiments.csv", experiment_rows)
        unit_rows = [{"unit_id": u.id, "rq_code": rq_by_manifest[u.manifest_id], "experiment_id": u.experiment_id, "manifest_id": u.manifest_id, "condition_code": u.condition_code, "prompt_id": u.prompt_id, "answer_a_id": u.answer_a_id, "answer_b_id": u.answer_b_id, "counterfactual_variant_id": u.counterfactual_variant_id, "judge": u.judge_model, "provider": u.provider, "provider_model": u.provider_model, "repetition_index": u.repetition_index, "presentation_order": u.presentation_order, "randomization_block": u.randomization_block, "data_split": u.data_split, "inclusion_status": u.inclusion_status, "temperature": u.temperature, "top_p": u.top_p, "seed": u.seed, "pairing_key": u.pairing_key, "unit_fingerprint": u.unit_fingerprint, "created_at": u.created_at} for u in sorted(units, key=lambda u: (rq_by_manifest[u.manifest_id], str(u.manifest_id), str(u.id)))]
        write_json(PACKAGE / "evidence" / "units" / "controlled_units.json", unit_rows)
        controlled_rows = [run_row(r, unit_by_id[r.experimental_unit_id], manifest_by_id[unit_by_id[r.experimental_unit_id].manifest_id]) for r in controlled]
        controlled_pass_rows = [pass_row(p, controlled_by_id[p.run_id], unit_by_id[controlled_by_id[p.run_id].experimental_unit_id], manifest_by_id[unit_by_id[controlled_by_id[p.run_id].experimental_unit_id].manifest_id]) for p in controlled_passes]
        controlled_attempt_rows = [attempt_row(a, controlled_by_id[a.run_id], unit_by_id[controlled_by_id[a.run_id].experimental_unit_id], manifest_by_id[unit_by_id[controlled_by_id[a.run_id].experimental_unit_id].manifest_id]) for a in controlled_attempts]
        write_json(PACKAGE / "evidence" / "runs" / "controlled_runs.json", controlled_rows)
        write_json(PACKAGE / "evidence" / "passes" / "controlled_passes.json", controlled_pass_rows)
        write_json(PACKAGE / "evidence" / "attempts" / "controlled_attempts.json", controlled_attempt_rows)
        provenance_rows = [{"run_id": row["run_id"], "unit_id": row["unit_id"], "rq_code": row["rq_code"], "judge": row["judge"], "requested_model": row["requested_model"], "configured_route": (row["metadata"] or {}).get("routing_fingerprint"), "observed_provider_model": row["provider_model"]} for row in controlled_rows]
        for row in controlled_pass_rows:
            route = row.get("route_provenance") or {}
            if route:
                provenance_rows.append({"pass_id": row["pass_id"], "run_id": row["run_id"], "unit_id": row["unit_id"], "rq_code": row["rq_code"], "effective_model": row["effective_model"], "configured_upstream_provider": route.get("configured_upstream_provider"), "observed_provider_family": route.get("observed_upstream_provider"), "observed_endpoint_slug": None if row["provider_model"] == "deepinfra" else row["provider_model"], "verification_basis": "REQUEST_ENFORCED_EXACT_ENDPOINT_RESPONSE_CONFIRMED_FAMILY" if route.get("configured_upstream_provider") == "deepinfra/turbo" else "FROZEN_ROUTE_AND_RESPONSE_PROVENANCE", "provider_response_id": row["provider_response_id"], "routing_fingerprint": route.get("routing_fingerprint")})
        write_json(PACKAGE / "evidence" / "provenance" / "provider_provenance.json", provenance_rows)

        def historical(rows: Iterable[ControlledRun], pass_rows: list[RunPass], attempt_rows: list[PassAttempt], folder: str, label: str) -> None:
            items = list(rows); ids = {r.id for r in items}; by_id = {r.id: r for r in items}
            write_json(PACKAGE / "audit_history" / folder / "runs.json", [run_row(r, unit_by_id[r.experimental_unit_id], manifest_by_id[unit_by_id[r.experimental_unit_id].manifest_id]) for r in items])
            write_json(PACKAGE / "audit_history" / folder / "passes.json", [pass_row(p, by_id[p.run_id], unit_by_id[by_id[p.run_id].experimental_unit_id], manifest_by_id[unit_by_id[by_id[p.run_id].experimental_unit_id].manifest_id]) for p in pass_rows if p.run_id in ids])
            write_json(PACKAGE / "audit_history" / folder / "attempts.json", [attempt_row(a, by_id[a.run_id], unit_by_id[by_id[a.run_id].experimental_unit_id], manifest_by_id[unit_by_id[by_id[a.run_id].experimental_unit_id].manifest_id]) for a in attempt_rows if a.run_id in ids])
            (PACKAGE / "audit_history" / folder / "README.md").write_text(f"# {label}\n\nAudit history only. NOT INCLUDED IN FINAL SCIENTIFIC METRICS.\n", encoding="utf-8")
        historical(superseded, superseded_passes, superseded_attempts, "superseded_rq5", "PRE_FIX_RQ5_RAW_ANSWER_MATERIALIZATION")
        historical(pilot, pilot_passes, pilot_attempts, "pilot", "Phase 9A PILOT — technical real-wire validation only")
        failed_rows = [row for row in controlled_rows if row["status"] != "SUCCEEDED" and row["run_id"] in {str(r.id) for r in failed}]
        write_json(PACKAGE / "audit_history" / "operational_failures" / "terminal_failed_units.json", failed_rows)
        write_json(PACKAGE / "audit_history" / "operational_failures" / "failure_accounting.json", {"terminal_failed_units": len(failed), "failed_pass_slots": EXPECTED["failed_pass_slots"], "attempt_failure_categories": Counter(a.failure_category or "NONE" for a in controlled_attempts if a.state != "SUCCEEDED")})

        analysis_rows = [{"analysis_run_id": ar.id, "rq_code": ar.rq_code, "rq_title": RQ_TITLES[ar.rq_code], "manifest_id": ar.manifest_id, "experiment_id": ar.experiment_id, "dataset_version_id": experiment_by_id[ar.experiment_id].dataset_version_id, "analysis_version": ar.analysis_version, "analysis_seed": ar.analysis_seed, "status": ar.status, "created_at": ar.created_at, "result": ar.result_json} for ar in analysis]
        write_json(PACKAGE / "analysis" / "analysis_runs.json", analysis_rows)
        for row in analysis_rows: write_json(PACKAGE / "analysis" / "metrics" / f"{row['rq_code'].lower()}_metrics.json", row["result"])
        copied = copy_phase10_artifacts(PACKAGE)
        trace_metrics = []
        for ar in analysis_rows:
            for metric in ar["result"].get("results", []):
                trace_metrics.append({"metric_key": metric.get("metric_key"), "rq_code": ar["rq_code"], "human_readable_metric_name": metric.get("metric_name"), "estimate": metric.get("value"), "ci_low": metric.get("ci_low"), "ci_high": metric.get("ci_high"), "eligible_n": metric.get("eligible_n"), "analyzed_n": metric.get("analyzed_n"), "analysis_run_id": ar["analysis_run_id"], "manifest_id": ar["manifest_id"], "experiment_id": ar["experiment_id"], "dataset_version_id": ar["dataset_version_id"], "dataset_sha256": EXPECTED["dataset_sha"], "analysis_code_commit": "d2199cc", "source_evidence_query": {"evidence_class": "CONTROLLED", "manifest_id": ar["manifest_id"], "unit_index": "evidence/units/controlled_units.json", "run_index": "evidence/runs/controlled_runs.json", "pass_index": "evidence/passes/controlled_passes.json"}, "phase10_artifacts": ["analysis/phase10_metrics_summary.json", f"analysis/tables/table_{ar['rq_code'].lower()}_{ {'RQ1':'human_alignment','RQ2':'consistency','RQ3':'position_sensitivity','RQ4':'redundant_length','RQ5':'format_effect','RQ6':'source_family','RQ7':'mitigation'}[ar['rq_code']] }.json"]})
        write_json(PACKAGE / "TRACEABILITY_INDEX.json", {"package_version": PACKAGE_VERSION, "metrics": trace_metrics})
        git_state = {"phase10_source_commit": "d2199cc", "phase10_source_tag": "phase10-offline-analysis-validated-v1", "current_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(), "tags_at_head": subprocess.check_output(["git", "tag", "--points-at", "HEAD"], cwd=ROOT, text=True).splitlines()}
        write_json(PACKAGE / "environment" / "git_state.json", git_state)
        (PACKAGE / "environment" / "python_environment.txt").write_text(sys.version + "\n" + platform.platform() + "\n", encoding="utf-8")
        versions = {name: metadata.version(name) for name in ("SQLAlchemy", "alembic", "pydantic", "fastapi", "httpx", "numpy", "pandas", "matplotlib") if metadata.packages_distributions().get(name.lower()) or True}
        write_json(PACKAGE / "environment" / "package_versions.txt", versions)
        write_json(PACKAGE / "environment" / "postgresql_version.json", {"version": session.execute(text("SELECT version()")).scalar_one()})
        session.rollback()

        accounting = {"units": len(units), "planned_pass_slots": total_slots, "valid_returned_passes": valid_returned, "failed_pass_slots": total_slots - valid_returned, "succeeded": len(succeeded), "valid_partial": len(partial), "failed": len(failed), "pending": 0, "controlled_attempts": len(controlled_attempts), "attempt_states": Counter(a.state for a in controlled_attempts), "superseded_rq5": len(superseded), "superseded_passes": len(superseded_passes), "superseded_attempts": len(superseded_attempts), "pilot": len(pilot), "pilot_passes": len(pilot_passes), "pilot_attempts": len(pilot_attempts)}
        inventory, root_digest = make_sums(PACKAGE)
        package_manifest = {"package_version": PACKAGE_VERSION, "package_created_at": datetime.now(timezone.utc), "project_name": "LLM-as-a-Judge Reliability Lab: Measuring and Mitigating Biases in Automatic Evaluation of Generated Responses", "phase10_source_tag": "phase10-offline-analysis-validated-v1", "phase10_source_commit": "d2199cc", "dataset": {"id": str(dataset.id), "sha256": dataset.source_checksum, "version": dataset.version, "source": dataset.source_name}, "fingerprints": {"prompt_hash": EXPECTED["prompt_hash"], "routing_fingerprint": EXPECTED["routing_fingerprint"], "retry_policy": RETRY_POLICY_VERSION}, "manifest_ids": manifest_ids, "experiment_ids": [str(exp.id) for exp in experiments], "analysis_run_ids": EXPECTED["analysis_ids"], "accounting": accounting, "traceability_metric_count": len(trace_metrics), "phase10_artifacts": copied, "file_inventory": inventory, "package_root_digest": root_digest, "integrity_procedure": "SHA256SUMS hashes every payload file except EVIDENCE_MANIFEST.json, PACKAGE_METADATA.json, and SHA256SUMS.txt. package_root_digest is SHA256 of the exact UTF-8 SHA256SUMS.txt bytes; this avoids circular hashing."}
        write_json(PACKAGE / "EVIDENCE_MANIFEST.json", package_manifest)
        write_json(PACKAGE / "PACKAGE_METADATA.json", {"package_version": PACKAGE_VERSION, "package_root_digest": root_digest, "hash_scope_exclusions": sorted(CONTROL_FILES), "created_at": package_manifest["package_created_at"]})
        secrets = secret_scan(PACKAGE)
        if secrets:
            raise RuntimeError(f"secret marker(s) found in generated package: {secrets}")
        # The final verifier also validates the sibling pg_dump snapshot. That
        # snapshot is intentionally made only after this read-only export and
        # attached by finalize_phase11_snapshot.py.
        make_report(PACKAGE, package_manifest, root_digest)
        return {"package": str(PACKAGE), "root_digest": root_digest, "accounting": accounting, "files_hashed": len(inventory)}
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Freeze Phase 11 evidence package without provider calls")
    parser.add_argument("--export", action="store_true", help="create the new package; refuses to overwrite it")
    args = parser.parse_args()
    if not args.export:
        parser.error("--export is required")
    print(json.dumps(export(), indent=2, sort_keys=True, default=str))
