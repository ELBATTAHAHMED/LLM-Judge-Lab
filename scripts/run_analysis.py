"""Verify the frozen corrected full-population analysis without provider calls."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from canonical_source_data import load_canonical_study, validate_canonical_source  # noqa: E402


ARTIFACT = ROOT / "evidence" / "remediation" / "source_corrected_complete_case_full_population_analysis_v2.json"


def main() -> int:
    argparse.ArgumentParser(description="Verify frozen source-corrected analysis outputs without provider calls.").parse_args()
    canonical, _ = validate_canonical_source()
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    expected = {
        "RQ1": ("exact_agreement", 0.5919689119170984),
        "RQ2": ("strict_complete_repetition_consistency", 0.9652881355932203),
        "RQ3": ("paired_decisive_flip_rate", 0.17486338797814208),
        "RQ4": ("variant_win_rate", 0.0),
        "RQ5": ("variant_win_rate", 0.0),
        "RQ6": ("stable_same_family_preference", 0.5094339622641509),
    }
    results = artifact["results"]
    for rq, (metric, value) in expected.items():
        assert results[rq][metric]["value"] == value, rq
    assert results["RQ7_PRIMARY"]["agreement_delta"]["value"] == 0.006700167504187605
    assert results["RQ7_SECONDARY"]["matched_delta"] == 0.050222222222222224
    print(json.dumps({"provider_calls": 0, "canonical_dataset_sha256": canonical["canonical_dataset_sha256"], "analysis_artifact_sha256": artifact["artifact_sha256"], "status": "VERIFIED"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
