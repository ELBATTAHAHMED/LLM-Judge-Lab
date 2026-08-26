"""Fail-closed contract tests for the promoted corrected RQ7 secondary."""
from types import SimpleNamespace
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from main import serialize_multi_judge_secondary
from backend.core.final_evidence import CORRECTED_ANALYSIS_VERSION, CORRECTED_ARTIFACT_SHA256

METRICS = {
    "planned_n": 1611, "consensus_covered_n": 1125, "agreement": .718222,
    "coverage": .698324, "equal_weight_individual_comparator": .668,
    "matched_delta": .050222, "matched_delta_ci_95": {"low": .041555, "high": .058888},
}


def row(**changes):
    payload = {"rq_key": "RQ7_SECONDARY", "analysis_artifact_identity": CORRECTED_ANALYSIS_VERSION, "artifact_sha256": CORRECTED_ARTIFACT_SHA256, "metrics": dict(METRICS)}
    payload.update(changes)
    return SimpleNamespace(
        id="id", rq_code=payload.pop("run_rq", "RQ7"),
        analysis_version=payload.pop("analysis_version", CORRECTED_ANALYSIS_VERSION),
        result_json=payload,
    )


def test_valid_secondary_serializes_without_direct_delta():
    value, error = serialize_multi_judge_secondary([row()])
    assert error is None
    result = value["multi_judge_consensus"]
    assert result["role"] == "SECONDARY"
    assert result["retained_n"] == 1125
    assert result["direct_dualswap_comparison"] == "NOT_DEFENSIBLE"
    assert "dualswap_delta" not in result


def test_missing_duplicate_wrong_rq_or_wrong_version_fail_closed():
    assert serialize_multi_judge_secondary([])[0] is None
    assert serialize_multi_judge_secondary([row(), row()])[0] is None
    assert serialize_multi_judge_secondary([row(run_rq="RQ6")])[0] is None
    assert serialize_multi_judge_secondary([row(analysis_version="other")])[0] is None


def test_missing_metric_ci_or_provenance_fails_closed_without_fallback():
    missing_metric = {key: value for key, value in METRICS.items() if key != "agreement"}
    missing_ci = {key: value for key, value in METRICS.items() if key != "matched_delta_ci_95"}
    malformed_ci = {**METRICS, "matched_delta_ci_95": {"low": .04}}
    for change in ({"metrics": missing_metric}, {"metrics": missing_ci}, {"metrics": malformed_ci}, {"artifact_sha256": ""}):
        value, error = serialize_multi_judge_secondary([row(**change)])
        assert value is None
        assert "invalid provenance contract" in error
