"""Provider-free, full-population source-corrected analysis.

This supersedes the remediation-subset Phase E computation without modifying its
artifact, its AnalysisRuns, execution ledgers, or any historical evidence.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.analysis.source_corrected_complete_case import (
    CompleteCaseAnalysisError,
    DATASET_VERSION,
    ITERATIONS,
    MULTIJUDGE_MANIFEST_SHA256,
    RECOVERY_MANIFEST_SHA,
    RQ6_MANIFEST_SHA256,
    _analysis_lineages,
    _by_rq,
    _historical_comparison,
    _rq1,
    _rq2,
    _rq3,
    _rq7_primary,
    _rq7_secondary,
    _variant,
    build_logical_view,
    complete_case_populations,
    reconcile_and_observations,
    load_preflight_manifest,
    analyze_counterbalanced_observations,
    stable_sha,
)
from backend.core.controlled_models import AnalysisRun
from backend.evaluation.persistence import to_json_safe


ROOT = Path(__file__).resolve().parent.parent.parent
ANALYSIS_VERSION = "source-corrected-complete-case-full-population-analysis-v2"
POLICY_IDENTITY = "source-corrected-complete-case-analysis-v1"
ARTIFACT_IDENTITY = "source-corrected-complete-case-full-population-analysis-v2"
OUTPUT_PATH = ROOT / "evidence" / "remediation" / "source_corrected_complete_case_full_population_analysis_v2.json"
CONTROLLED_SEED = 20260818
MULTIJUDGE_SEED = 20260823
PROVISIONAL_RUN_IDS = {
    "RQ1": "4faebc39-efb1-4472-afd9-ae1a348e393a",
    "RQ2": "5b5f8ddd-5ee8-4e75-a6ea-fe42db42f7da",
    "RQ3": "7aaeaae3-bc9d-4065-b8c0-63343e14188d",
    "RQ4": "eedb918e-3102-4a20-84e8-b80e8afc589f",
    "RQ5": "249f0263-9cf8-4658-a28c-518bd8cadaff",
    "RQ6": "d87d1871-b8ff-4d60-a3ed-8ddfb1e31106",
    "RQ7_PRIMARY": "4c32a8e1-0186-4c74-a401-8102895869e7",
    "RQ7_SECONDARY": "e45c13d4-5ab0-4b10-90e3-31cbd7152293",
}


def _metric(metrics: dict[str, Any], name: str) -> dict[str, Any]:
    value = metrics.get(name)
    if not isinstance(value, dict):
        raise CompleteCaseAnalysisError(f"missing expected metric {name}")
    return value


def _lineage_counts(logical: list[Any], populations: dict[str, Any], results: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "RQ1": {"planned": 800, "physical": 798, "analytical": 772},
        "RQ2": {"planned": 1600, "physical": 1599, "analytical": 1475, "conditional": 1585},
        "RQ3": {"planned": 800, "physical": 799, "analytical": 549, "valid": 759},
        "RQ4": {"planned": 800, "physical": 799, "analytical": 682},
        "RQ5": {"planned": 800, "physical": 800, "analytical": 716},
        "RQ7_PRIMARY": {"planned": 800, "physical": 799, "analytical": 597},
    }
    output: dict[str, Any] = {}
    for rq, checks in expected.items():
        rows = _by_rq(logical, rq, include_reusable=True)
        source_counts = {
            "SOURCE_CORRECT_REUSABLE": sum(row.source == "SOURCE_CORRECT_REUSABLE" for row in rows),
            "CORRECTED_ORIGINAL": sum(row.source == "CORRECTED_ORIGINAL" for row in rows),
            "RECOVERY_REPLACEMENT": sum(row.source == "RECOVERY_REPLACEMENT" and row.outcome is not None for row in rows),
            "TERMINAL_MISSING": sum(row.outcome is None for row in rows),
        }
        source_sum = sum(source_counts.values())
        if rq == "RQ1":
            planned, physical = populations[rq]["planned"], populations[rq]["available_independent_observations"]
            analytical = _metric(results[rq], "exact_agreement")["denominator"]
        elif rq == "RQ2":
            planned, physical = populations[rq]["planned_cells"], populations[rq]["complete_five_repetition_cells"]
            analytical = _metric(results[rq], "strict_complete_repetition_consistency")["denominator"]
        elif rq == "RQ3":
            planned, physical = populations[rq]["planned_pairs"], populations[rq]["complete_ab_ba_pairs"]
            analytical = _metric(results[rq], "paired_decisive_flip_rate")["denominator"]
        elif rq in {"RQ4", "RQ5"}:
            planned, physical = populations[rq]["planned_pairs"], populations[rq]["complete_matched_pairs"]
            analytical = _metric(results[rq], "variant_win_rate")["denominator"]
        else:
            planned, physical = populations[rq]["planned_triplets"], populations[rq]["complete_linked_triplets"]
            analytical = _metric(results[rq], "agreement_delta")["denominator"]
        actual = {"planned": planned, "physical": physical, "analytical": analytical}
        if rq == "RQ2":
            actual["conditional"] = _metric(results[rq], "conditional_returned_judgment_consistency")["denominator"]
        if rq == "RQ3":
            actual["valid"] = _metric(results[rq], "all_paired_disagreement_rate")["denominator"]
        if source_sum != {"RQ1": 800, "RQ2": 8000, "RQ3": 1600, "RQ4": 1600, "RQ5": 1600, "RQ7_PRIMARY": 2400}[rq]:
            raise CompleteCaseAnalysisError(f"{rq} full source-precedence pass count does not reconcile")
        if actual != checks:
            raise CompleteCaseAnalysisError(f"{rq} full-population counts mismatch: {actual!r} != {checks!r}")
        output[rq] = {"selected_logical_passes": source_sum, "sources": source_counts, **actual}
    output["RQ6"] = {"planned": 480, "physical": 480, "analytical": _metric(results["RQ6"], "stable_same_family_preference")["denominator"], "source": "frozen_counterbalanced_lineage"}
    secondary = results["RQ7_SECONDARY"]
    output["RQ7_SECONDARY"] = {
        "planned": secondary["planned_n"], "four_valid": secondary["four_valid_n"],
        "covered": secondary["consensus_covered_n"], "affected": secondary["remediation_subset_planned_n"],
        "unmodified_historical": secondary["planned_n"] - secondary["remediation_subset_planned_n"],
    }
    if output["RQ6"]["analytical"] != 159 or output["RQ7_SECONDARY"] != {
        "planned": 1611, "four_valid": 1482, "covered": 1125, "affected": 498, "unmodified_historical": 1113,
    }:
        raise CompleteCaseAnalysisError("RQ6 or RQ7 secondary full-population count mismatch")
    return output


def compute(session: Session, *, iterations: int = ITERATIONS) -> dict[str, Any]:
    logical, accounting, artifacts = build_logical_view(session)
    if not accounting["no_double_count"] or accounting["source_correct_reusable_passes"] != 13103:
        raise CompleteCaseAnalysisError("full logical source-precedence integrity check failed")
    populations = complete_case_populations(logical, include_reusable=True)
    rq1 = _rq1(_by_rq(logical, "RQ1", include_reusable=True), seed=CONTROLLED_SEED, iterations=iterations)
    rq2 = _rq2(_by_rq(logical, "RQ2", include_reusable=True), seed=CONTROLLED_SEED, iterations=iterations)
    rq3 = _rq3(_by_rq(logical, "RQ3", include_reusable=True), seed=CONTROLLED_SEED, iterations=iterations)
    rq4 = _variant(_by_rq(logical, "RQ4", include_reusable=True), "RQ4", seed=CONTROLLED_SEED, iterations=iterations)
    rq5 = _variant(_by_rq(logical, "RQ5", include_reusable=True), "RQ5", seed=CONTROLLED_SEED, iterations=iterations)
    rq6_manifest = load_preflight_manifest()
    rq6 = {
        key: value.serialize()
        for key, value in analyze_counterbalanced_observations(
            reconcile_and_observations(session, rq6_manifest), seed=CONTROLLED_SEED, iterations=iterations,
        ).items()
    }
    rq7_primary = _rq7_primary(
        _by_rq(logical, "RQ7_PRIMARY", include_reusable=True), seed=CONTROLLED_SEED,
        iterations=iterations, expected_complete_case_count=799,
    )
    rq7_secondary = _rq7_secondary(session, artifacts["manifest"], seed=MULTIJUDGE_SEED, iterations=iterations)
    results = {
        "RQ1": rq1, "RQ2": rq2, "RQ3": rq3, "RQ4": rq4, "RQ5": rq5,
        "RQ6": rq6, "RQ7_PRIMARY": rq7_primary, "RQ7_SECONDARY": rq7_secondary,
    }
    lineage_counts = _lineage_counts(logical, populations, results)
    policy = {
        "identity": POLICY_IDENTITY,
        "scope": "FULL_POPULATION_SOURCE_PRECEDENCE",
        "source_precedence": ["SOURCE_CORRECT_REUSABLE", "CORRECTED_ORIGINAL", "RECOVERY_REPLACEMENT", "TERMINAL_MISSING"],
        "no_imputation": True, "no_model_substitution": True, "no_parser_relaxation": True,
        "additional_provider_calls": 0,
        "estimators": {
            "RQ4": "validated stable controlled redundant-text variant wins / valid controlled pairs; numerator variant_outcome == VARIANT",
            "RQ5": "validated stable controlled presentation/list-prefix variant wins / valid controlled pairs; numerator variant_outcome == VARIANT",
        },
        "seeds": {"controlled_and_rq6": CONTROLLED_SEED, "rq7_secondary_multijudge": MULTIJUDGE_SEED},
        "bootstrap_iterations": iterations,
    }
    result = {
        "artifact_identity": ARTIFACT_IDENTITY, "analysis_version": ANALYSIS_VERSION,
        "dataset_version": DATASET_VERSION, "policy": policy,
        "lineage": {
            "corrected_manifest_sha256": artifacts["manifest"]["manifest_sha256"],
            "recovery_manifest_sha256": RECOVERY_MANIFEST_SHA, "rq6_manifest_sha256": RQ6_MANIFEST_SHA256,
            "historical_multijudge_manifest_sha256": MULTIJUDGE_MANIFEST_SHA256,
        },
        "full_population_lineage_counts": lineage_counts,
        "complete_case_populations": populations,
        "logical_observation_accounting": accounting,
        "results": results,
        "historical_comparison": _historical_comparison(session, results),
        "provisional_superseded_analysis_runs": PROVISIONAL_RUN_IDS,
        "provider_activity": {"provider_calls": 0, "spend_usd": "0"},
        "promotion_status": "NOT_PROMOTED",
    }
    result["artifact_sha256"] = stable_sha({key: value for key, value in result.items() if key != "artifact_sha256"})
    return result


def _payload(result: dict[str, Any], rq_key: str) -> dict[str, Any]:
    return {
        "evidence_class": "CONTROLLED", "dataset_version": DATASET_VERSION,
        "analysis_policy": POLICY_IDENTITY, "analysis_scope": "FULL_POPULATION_SOURCE_PRECEDENCE",
        "analysis_artifact_identity": ARTIFACT_IDENTITY, "artifact_sha256": result["artifact_sha256"],
        "rq_key": rq_key, "metrics": result["results"][rq_key],
        "frozen_seed": MULTIJUDGE_SEED if rq_key == "RQ7_SECONDARY" else CONTROLLED_SEED,
        "provisional_superseded_analysis_run_id": PROVISIONAL_RUN_IDS[rq_key],
        "full_population_lineage_counts": result["full_population_lineage_counts"],
        "provider_activity": result["provider_activity"], "promotion_status": "NOT_PROMOTED",
    }


def publish(session: Session, result: dict[str, Any]) -> dict[str, str]:
    lineages = _analysis_lineages(session)
    output: dict[str, str] = {}
    for rq_key in PROVISIONAL_RUN_IDS:
        base_rq = "RQ7" if rq_key.startswith("RQ7") else rq_key
        experiment, manifest = lineages[base_rq]
        payload = to_json_safe(_payload(result, rq_key))
        existing = list(session.scalars(select(AnalysisRun).where(
            AnalysisRun.manifest_id == manifest.id, AnalysisRun.rq_code == base_rq,
            AnalysisRun.analysis_version == ANALYSIS_VERSION,
        )).all())
        matching = [row for row in existing if (row.result_json or {}).get("rq_key") == rq_key]
        if len(matching) > 1:
            raise CompleteCaseAnalysisError(f"ambiguous full-population AnalysisRun for {rq_key}")
        if matching:
            row = matching[0]
            if row.status != "COMPLETED" or row.result_json != payload:
                raise CompleteCaseAnalysisError(f"full-population AnalysisRun payload drift for {rq_key}")
        else:
            row = AnalysisRun(
                experiment_id=experiment.id, manifest_id=manifest.id, rq_code=base_rq,
                analysis_version=ANALYSIS_VERSION,
                analysis_seed=MULTIJUDGE_SEED if rq_key == "RQ7_SECONDARY" else CONTROLLED_SEED,
                status="COMPLETED", result_json=payload,
            )
            session.add(row)
            session.flush()
        output[rq_key] = str(row.id)
    return output


def write_artifact(result: dict[str, Any], run_ids: dict[str, str]) -> None:
    OUTPUT_PATH.write_text(json.dumps({**result, "analysis_run_ids": run_ids}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_existing(session: Session) -> None:
    material = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    core = {key: value for key, value in material.items() if key not in {"artifact_sha256", "analysis_run_ids"}}
    if material.get("artifact_identity") != ARTIFACT_IDENTITY or material.get("artifact_sha256") != stable_sha(core):
        raise CompleteCaseAnalysisError("full-population artifact identity or SHA mismatch")
    if material.get("policy", {}).get("seeds") != {"controlled_and_rq6": CONTROLLED_SEED, "rq7_secondary_multijudge": MULTIJUDGE_SEED}:
        raise CompleteCaseAnalysisError("frozen seed provenance mismatch")
    if material.get("provisional_superseded_analysis_runs") != PROVISIONAL_RUN_IDS:
        raise CompleteCaseAnalysisError("provisional AnalysisRun lineage mismatch")
    for rq_key, run_id in (material.get("analysis_run_ids") or {}).items():
        row = session.get(AnalysisRun, run_id)
        if row is None or row.status != "COMPLETED" or row.analysis_version != ANALYSIS_VERSION:
            raise CompleteCaseAnalysisError(f"missing full-population AnalysisRun for {rq_key}")
        if (row.result_json or {}).get("artifact_sha256") != material["artifact_sha256"]:
            raise CompleteCaseAnalysisError(f"full-population AnalysisRun provenance mismatch for {rq_key}")
    for rq_key, provisional_id in PROVISIONAL_RUN_IDS.items():
        row = session.get(AnalysisRun, provisional_id)
        if row is None or (row.result_json or {}).get("analysis_policy") != POLICY_IDENTITY:
            raise CompleteCaseAnalysisError(f"provisional AnalysisRun missing or modified for {rq_key}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--iterations", type=int, default=ITERATIONS)
    args = parser.parse_args()
    if args.iterations != 10_000:
        raise CompleteCaseAnalysisError("full-population scientific analysis requires frozen 10,000 resamples")
    from backend.core.database import SessionLocal
    with SessionLocal() as session:
        if args.verify:
            verify_existing(session)
            print("SOURCE_CORRECTED_FULL_POPULATION_ANALYSIS_VERIFIED")
            return 0
        result = compute(session, iterations=args.iterations)
        run_ids = publish(session, result) if args.publish else {}
        if args.publish:
            session.commit()
    if args.publish:
        write_artifact(result, run_ids)
    if args.summary:
        print(json.dumps({"artifact_sha256": result["artifact_sha256"], "lineage_counts": result["full_population_lineage_counts"], "results": result["results"], "provider_calls": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
