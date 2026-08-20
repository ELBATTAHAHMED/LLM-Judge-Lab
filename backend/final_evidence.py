"""Pinned identifiers for the final controlled evidence release.

The application may contain legacy and later exploratory AnalysisRuns.  The
final-results route must therefore select this release explicitly rather than
using recency as a proxy for authority.
"""
from __future__ import annotations

from typing import Any, Iterable


CANONICAL_FINAL_ANALYSIS_RUNS: dict[str, str] = {
    "RQ1": "63cd1939-05f4-42cf-a933-4094ac652eea",
    "RQ2": "4013c629-44bf-4021-860b-5c5caba6a8d2",
    "RQ3": "28e45929-c042-4578-be2f-d8f30082b693",
    "RQ4": "057a5a79-0b44-4ba3-9dbb-2d9d01590728",
    "RQ5": "a729804a-5539-400f-998f-83b8c6ada30a",
    "RQ6": "ca2bd7a4-88dc-4be5-883d-cd8f849aa5fa",
    "RQ7": "fa24666d-b4c9-4b1d-a767-cfc59c4380ac",
}

CANONICAL_FINAL_MANIFESTS: dict[str, str] = {
    "RQ1": "550e0ec5-e531-45fa-a1ea-422cc9710001",
    "RQ2": "0581763f-1fff-4092-a2f2-c60170eb8dbf",
    "RQ3": "816ba9b6-1dd4-40ac-abed-15e3e4dd896a",
    "RQ4": "f63360e4-04c8-4815-86b5-eefeed78cb5b",
    "RQ5": "494cf45e-f974-4f92-bc8f-f490d82d0f91",
    "RQ6": "6a8f5b74-3e26-4d28-ba6d-b39d021d83eb",
    "RQ7": "55e58905-2265-49b3-87b7-1d55daa073ea",
}

# Phase 11 is immutable historical provenance.  Its original RQ6 record
# remains preserved here rather than being mistaken for the active repaired
# counterbalanced result.
HISTORICAL_PHASE11_RQ6 = {
    "analysis_run_id": "ca9a1668-58b9-4a9d-8b0d-991c2b7a38ec",
    "manifest_id": "5491bd7b-2f59-4922-a4c2-ecbe38c57e0a",
    "status": "NOT_ESTIMABLE — UNBALANCED_PRESENTATION",
}

# These original records remain pinned only for immutable Phase 11
# reproducibility checks.  They are intentionally distinct from the active
# current-release map above.
PHASE11_HISTORICAL_FINAL_ANALYSIS_RUNS: dict[str, str] = {
    "RQ1": "63cd1939-05f4-42cf-a933-4094ac652eea",
    "RQ2": "25949bbe-b962-4808-9830-f106bb3d1d42",
    "RQ3": "4a5a5c97-6b63-4d33-9129-3d7048e96a87",
    "RQ4": "13510c83-354c-49b1-811f-5e96a6b985e7",
    "RQ5": "bbfbcf03-1791-4892-a39c-418831260f35",
    "RQ6": HISTORICAL_PHASE11_RQ6["analysis_run_id"],
    "RQ7": "d3773e0c-80dc-4235-aa46-ffd89af9face",
}

PHASE11_HISTORICAL_FINAL_MANIFESTS: dict[str, str] = {
    **{rq: manifest_id for rq, manifest_id in CANONICAL_FINAL_MANIFESTS.items() if rq != "RQ6"},
    "RQ6": HISTORICAL_PHASE11_RQ6["manifest_id"],
}


def canonical_final_analysis_runs(rows: Iterable[Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Validate and order exactly the seven final AnalysisRuns.

    This deliberately ignores any additional AnalysisRuns.  A missing or
    incompatible canonical record makes the final route fail closed.
    """
    by_id = {str(row.id): row for row in rows}
    missing = [run_id for run_id in CANONICAL_FINAL_ANALYSIS_RUNS.values() if run_id not in by_id]
    if missing:
        return None, "Canonical final AnalysisRun records are missing."

    selected: dict[str, Any] = {}
    for rq_code, run_id in CANONICAL_FINAL_ANALYSIS_RUNS.items():
        row = by_id[run_id]
        if row.rq_code != rq_code or str(row.manifest_id) != CANONICAL_FINAL_MANIFESTS[rq_code]:
            return None, "Canonical final AnalysisRun provenance does not match its RQ/manifest."
        if row.status != "COMPLETED" or (row.result_json or {}).get("evidence_class") != "CONTROLLED":
            return None, "Canonical final AnalysisRun is not completed CONTROLLED evidence."
        selected[rq_code] = row
    return selected, None
