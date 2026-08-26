"""Verify or independently recompute the frozen corrected full-population analysis without provider calls."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.data.canonical import validate_canonical_source  # noqa: E402


ARTIFACT = ROOT / "evidence" / "remediation" / "source_corrected_complete_case_full_population_analysis_v2.json"

EXPECTED_METRICS = {
    "RQ1": ("exact_agreement", 0.5919689119170984),
    "RQ2": ("strict_complete_repetition_consistency", 0.9652881355932204),
    "RQ3": ("paired_decisive_flip_rate", 0.17486338797814208),
    "RQ4": ("variant_win_rate", 0.0),
    "RQ5": ("variant_win_rate", 0.0),
    "RQ6": ("stable_same_family_preference", 0.5094339622641509),
}
EXPECTED_RQ7_PRIMARY = 0.006700167504187605
EXPECTED_RQ7_SECONDARY = 0.050222222222222224


def verify_results_dict(results: dict) -> None:
    for rq, (metric, value) in EXPECTED_METRICS.items():
        actual = results[rq][metric]["value"]
        if actual != value:
            raise ValueError(f"{rq} {metric} mismatch: expected {value}, got {actual}")
    actual_rq7_p = results["RQ7_PRIMARY"]["agreement_delta"]["value"]
    if actual_rq7_p != EXPECTED_RQ7_PRIMARY:
        raise ValueError(f"RQ7_PRIMARY agreement_delta mismatch: expected {EXPECTED_RQ7_PRIMARY}, got {actual_rq7_p}")
    actual_rq7_s = results["RQ7_SECONDARY"]["matched_delta"]
    if actual_rq7_s != EXPECTED_RQ7_SECONDARY:
        raise ValueError(f"RQ7_SECONDARY matched_delta mismatch: expected {EXPECTED_RQ7_SECONDARY}, got {actual_rq7_s}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify or independently recompute source-corrected analysis outputs without provider calls."
    )
    parser.add_argument(
        "--recompute-from-db",
        action="store_true",
        help="Independently recompute full-population RQ1-RQ7 metrics from the database without provider calls.",
    )
    args = parser.parse_args()

    canonical, _ = validate_canonical_source()
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    if args.recompute_from_db:
        from backend.core.database import SessionLocal
        from backend.analysis.source_corrected_full_population import compute

        with SessionLocal() as session:
            recomputed = compute(session)

        verify_results_dict(recomputed["results"])

        if recomputed["artifact_sha256"] != artifact["artifact_sha256"]:
            raise ValueError(
                f"Recomputed artifact SHA mismatch: expected {artifact['artifact_sha256']}, got {recomputed['artifact_sha256']}"
            )

        print(
            json.dumps(
                {
                    "mode": "DATABASE_RECOMPUTATION",
                    "provider_calls": 0,
                    "canonical_dataset_sha256": canonical["canonical_dataset_sha256"],
                    "analysis_artifact_sha256": artifact["artifact_sha256"],
                    "recomputed_artifact_sha256": recomputed["artifact_sha256"],
                    "status": "VERIFIED",
                },
                sort_keys=True,
            )
        )
        return 0

    verify_results_dict(artifact["results"])
    print(
        json.dumps(
            {
                "analysis_artifact_sha256": artifact["artifact_sha256"],
                "canonical_dataset_sha256": canonical["canonical_dataset_sha256"],
                "provider_calls": 0,
                "status": "VERIFIED",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

