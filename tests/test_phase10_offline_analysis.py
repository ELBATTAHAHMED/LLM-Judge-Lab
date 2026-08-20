import json
from pathlib import Path
import pytest
from database import SessionLocal
from controlled_models import (
    AnalysisRun, ExperimentManifest, Experiment, ExperimentalUnit, ControlledRun
)
from controlled_analysis_adapter import (
    rq1_from_run, rq2_from_run, rq3_from_run, rq4_from_run, rq5_from_run, rq6_from_run, rq7_observations
)
from phase4_metrics import (
    analyze_rq1, analyze_rq2, analyze_rq3, analyze_rq4, analyze_rq5, analyze_rq6, analyze_rq7,
    ANALYSIS_VERSION
)

ROOT_DIR = Path(__file__).resolve().parent.parent
EXPORTS_DIR = ROOT_DIR / "exports" / "phase10"


def test_phase10_published_analysis_runs_all_completed():
    session = SessionLocal()
    try:
        runs = session.query(AnalysisRun).order_by(AnalysisRun.rq_code).all()
        assert len(runs) == 7
        for r in runs:
            assert r.status == "COMPLETED"
            assert r.analysis_version == ANALYSIS_VERSION
            assert r.analysis_seed == 20260818
            assert "results" in r.result_json
            assert len(r.result_json["results"]) > 0
    finally:
        session.close()


def test_phase10_offline_recomputation_exact_match_rq1_to_rq7():
    session = SessionLocal()
    try:
        manifests = session.query(ExperimentManifest).order_by(ExperimentManifest.rq_code).all()
        all_units = session.query(ExperimentalUnit).all()
        all_controlled_runs = [
            r for r in session.query(ControlledRun).all()
            if (r.metadata_json or {}).get("evidence_class") == "CONTROLLED"
        ]
        runs_by_unit = {r.experimental_unit_id: r for r in all_controlled_runs}
        units_by_manifest = {m.id: [u for u in all_units if u.manifest_id == m.id] for m in manifests}

        seed = 20260818
        iterations = 10_000

        for m in manifests:
            rq = m.rq_code
            units = units_by_manifest[m.id]
            pairs = [(runs_by_unit[unit.id], unit) for unit in units if unit.id in runs_by_unit]

            if rq == "RQ1":
                recomputed = analyze_rq1([rq1_from_run(r, u) for r, u in pairs], seed=seed, iterations=iterations)
            elif rq == "RQ2":
                recomputed = analyze_rq2([rq2_from_run(r, u, seed_policy="provider-recorded") for r, u in pairs], seed=seed, iterations=iterations)
            elif rq == "RQ3":
                recomputed = analyze_rq3([rq3_from_run(r, u) for r, u in pairs], seed=seed, iterations=iterations)
            elif rq == "RQ4":
                recomputed = analyze_rq4([rq4_from_run(r, u) for r, u in pairs], seed=seed, iterations=iterations)
            elif rq == "RQ5":
                recomputed = analyze_rq5([rq5_from_run(r, u) for r, u in pairs], seed=seed, iterations=iterations)
            elif rq == "RQ6":
                recomputed = analyze_rq6([rq6_from_run(r, u) for r, u in pairs], seed=seed, iterations=iterations)
            elif rq == "RQ7":
                recomputed = analyze_rq7(rq7_observations(pairs), seed=seed, iterations=iterations)

            ar = session.query(AnalysisRun).filter(AnalysisRun.manifest_id == m.id).first()
            assert ar is not None
            pub_results = {r["metric_key"]: r for r in ar.result_json["results"]}

            for k, metric in recomputed.items():
                assert k in pub_results
                pub_row = pub_results[k]
                if metric.value is not None:
                    assert abs(metric.value - pub_row["value"]) < 1e-9
                else:
                    assert pub_row["value"] is None

                if metric.ci_low is not None:
                    assert abs(metric.ci_low - pub_row["ci_low"]) < 1e-9
                if metric.ci_high is not None:
                    assert abs(metric.ci_high - pub_row["ci_high"]) < 1e-9
    finally:
        session.close()


def test_phase10_superseded_and_pilot_exclusion_in_analysis():
    session = SessionLocal()
    try:
        all_runs = session.query(ControlledRun).all()
        pilot_runs = [r for r in all_runs if (r.metadata_json or {}).get("evidence_class") == "PILOT"]
        superseded_runs = [r for r in all_runs if (r.metadata_json or {}).get("evidence_class") == "SUPERSEDED_CONTROLLED"]
        controlled_runs = [r for r in all_runs if (r.metadata_json or {}).get("evidence_class") == "CONTROLLED"]

        assert len(pilot_runs) == 11
        assert len(superseded_runs) == 226
        assert len(controlled_runs) == 13400

        # Verify analysis source unit IDs include only CONTROLLED units
        for ar in session.query(AnalysisRun).all():
            payload = ar.result_json
            assert payload["evidence_class"] == "CONTROLLED"
    finally:
        session.close()


def test_phase10_rq7_baseline_and_dual_swap_separation():
    session = SessionLocal()
    try:
        m_rq7 = session.query(ExperimentManifest).filter(ExperimentManifest.rq_code == "RQ7").first()
        units = session.query(ExperimentalUnit).filter(ExperimentalUnit.manifest_id == m_rq7.id).all()
        baseline_units = [u for u in units if u.condition_code == "BASELINE_STANDARD"]
        dual_units = [u for u in units if u.condition_code == "DUAL_SWAP"]

        assert len(baseline_units) == 800
        assert len(dual_units) == 800

        c_runs = [
            r for r in session.query(ControlledRun).filter(ControlledRun.experimental_unit_id.in_([u.id for u in units])).all()
            if (r.metadata_json or {}).get("evidence_class") == "CONTROLLED"
        ]
        runs_by_unit = {r.experimental_unit_id: r for r in c_runs}

        baseline_passes = sum(len(runs_by_unit[u.id].passes) for u in baseline_units if u.id in runs_by_unit)
        dual_passes = sum(len(runs_by_unit[u.id].passes) for u in dual_units if u.id in runs_by_unit)

        assert baseline_passes == 800
        assert dual_passes == 1600
        assert baseline_passes + dual_passes == 2400
    finally:
        session.close()


def test_phase10_exported_tables_and_charts_exist():
    required_tables = [
        "table_rq1_human_alignment",
        "table_rq2_consistency",
        "table_rq3_position_sensitivity",
        "table_rq4_redundant_length",
        "table_rq5_format_effect",
        "table_rq6_source_family",
        "table_rq7_mitigation",
        "table_cross_judge_summary",
        "table_failure_accounting",
        "table_analysis_provenance",
    ]
    for t in required_tables:
        csv_file = EXPORTS_DIR / "tables" / f"{t}.csv"
        json_file = EXPORTS_DIR / "tables" / f"{t}.json"
        assert csv_file.exists() and csv_file.stat().st_size > 0
        assert json_file.exists() and json_file.stat().st_size > 0

    assert (EXPORTS_DIR / "phase10_metrics_summary.json").exists()
    assert (EXPORTS_DIR / "phase10_analysis_provenance.json").exists()

    required_charts = [
        "rq1_agreement_by_judge.png",
        "rq1_kappa_by_judge.png",
        "rq2_consistency_by_judge.png",
        "rq3_paired_flip_rate_by_judge.png",
        "rq3_slot_win_imbalance.png",
        "rq4_variant_preference_by_judge.png",
        "rq5_format_preference_by_judge.png",
        "rq7_baseline_vs_dual_swap_alignment.png",
        "rq7_coverage_tradeoff.png",
        "cross_judge_synthesis.png",
    ]
    for c in required_charts:
        chart_file = EXPORTS_DIR / "charts" / c
        assert chart_file.exists() and chart_file.stat().st_size > 0
