"""Freeze the additive source-text-corrected controlled evidence package."""
from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from pathlib import Path

from controlled_models import AnalysisRun
from database import SessionLocal
from final_evidence import CANONICAL_FINAL_ANALYSIS_RUNS, CANONICAL_RQ7_SECONDARY_ANALYSIS_RUN, CORRECTED_ANALYSIS_VERSION, CORRECTED_ARTIFACT_SHA256

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "evidence" / "final" / "controlled_source_text_corrected_v1"
SOURCE = ROOT / "evidence" / "remediation"
SOURCES = ("source_text_reconciliation_v1.json", "controlled_source_text_corrected_preflight_v1.json", "controlled_source_text_corrected_execution_manifest_v1.json", "source_corrected_recovery_amendment_v1.json", "source_corrected_recovery_manifest_v1.json", "source_corrected_complete_case_full_population_analysis_v2.json")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def export_runs() -> dict[str, object]:
    ids = {**CANONICAL_FINAL_ANALYSIS_RUNS, "RQ7_SECONDARY": CANONICAL_RQ7_SECONDARY_ANALYSIS_RUN}
    with SessionLocal() as session:
        rows = {key: session.get(AnalysisRun, uuid.UUID(value)) for key, value in ids.items()}
    if any(row is None for row in rows.values()):
        raise RuntimeError("A source-corrected authoritative AnalysisRun is missing")
    output: dict[str, object] = {}
    for key, row in rows.items():
        assert row is not None
        payload = row.result_json or {}
        expected_key = "RQ7_PRIMARY" if key == "RQ7" else key
        if row.status != "COMPLETED" or row.analysis_version != CORRECTED_ANALYSIS_VERSION or payload.get("artifact_sha256") != CORRECTED_ARTIFACT_SHA256 or payload.get("rq_key") != expected_key:
            raise RuntimeError(f"Authoritative AnalysisRun contract mismatch: {key}")
        output[key] = {"id": str(row.id), "rq_code": row.rq_code, "manifest_id": str(row.manifest_id), "analysis_version": row.analysis_version, "analysis_seed": row.analysis_seed, "status": row.status, "result_json": payload}
    return output


def main() -> int:
    PACKAGE.mkdir(parents=True, exist_ok=True)
    source_dir = PACKAGE / "source"; source_dir.mkdir(exist_ok=True)
    for name in SOURCES:
        source = SOURCE / name
        if not source.exists():
            raise RuntimeError(f"Required source artifact is missing: {source}")
        shutil.copyfile(source, source_dir / name)
    write_json(PACKAGE / "dataset_provenance.json", {"dataset_name": "LMSYS MT-Bench Human Judgments", "dataset_identifier": "lmsys/mt_bench_human_judgments", "citation": "Zheng et al. (2023), Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena, arXiv:2306.05685", "dataset_license": "CC BY 4.0", "fastchat_code_license": "Apache-2.0", "raw_human_rows_local_upstream_matched": {"matched": 3355, "total": 3355}, "controlled_source_reconciliation": {"resolved": 1568, "total": 1568, "SOURCE_EXACT": 1070, "SOURCE_CORRECTION_REQUIRED": 498, "UNRESOLVED": 0}})
    write_json(PACKAGE / "correction_transparency.json", {"historical_issue": "Historical DB ingestion selected answers by insertion order, causing source-text mismatch for 498 controlled reference records.", "upstream_human_judgment_dataset_corrupted": False, "remediation": "Deterministic source reconciliation identified exact source responses; affected evaluations were rerun additively; historical evidence remained immutable.", "analysis_policy": "Full-population source precedence with explicit complete-case populations; no imputation, model substitution, or parser relaxation.", "terminal_missingness": "Fourteen terminal Claude observations remained unavailable after bounded recovery. Provider response identifiers were retained, but raw rejected response bodies were not persisted, preventing scientifically defensible offline re-parsing. The missing observations are judge-specific and concentrated in a small subset of questions, turns, and categories. Analyses therefore use explicitly reported complete-case populations, without claiming MCAR or MAR.", "provider_calls_for_freeze": 0})
    write_json(PACKAGE / "authoritative_analysis_runs.json", export_runs())
    shutil.copyfile(ROOT / "backend" / "verify_source_text_corrected_evidence.py", PACKAGE / "VERIFY_PACKAGE.py")
    files = sorted(path for path in PACKAGE.rglob("*") if path.is_file() and path.name != "package_manifest.json")
    inventory = [{"path": path.relative_to(PACKAGE).as_posix(), "sha256": sha256(path)} for path in files]
    lines = "".join(row["sha256"] + "  " + row["path"] + "\n" for row in sorted(inventory, key=lambda row: row["path"]))
    manifest = {"package_id": "controlled-source-text-corrected-v1", "version": 1, "immutable_additive_package": True, "provider_calls": 0, "authoritative_analysis": {"identity": CORRECTED_ANALYSIS_VERSION, "artifact_sha256": CORRECTED_ARTIFACT_SHA256}, "authoritative_analysis_runs": {**CANONICAL_FINAL_ANALYSIS_RUNS, "RQ7_SECONDARY": CANONICAL_RQ7_SECONDARY_ANALYSIS_RUN}, "file_inventory": inventory, "root_digest_algorithm": "SHA-256 of sorted UTF-8 SHA256<two spaces>relative_posix_path lines; manifest excluded to avoid self-reference", "package_root_digest": hashlib.sha256(lines.encode()).hexdigest()}
    write_json(PACKAGE / "package_manifest.json", manifest)
    print(json.dumps({"package": str(PACKAGE), "root_digest": manifest["package_root_digest"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
