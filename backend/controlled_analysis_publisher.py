"""Persist the only API-consumable representation of controlled metrics."""
from __future__ import annotations

from typing import Iterable, Mapping

from sqlalchemy.orm import Session

from controlled_models import AnalysisRun, ControlledRun, Experiment, ExperimentManifest, ExperimentalUnit
from controlled_analysis_adapter import rq1_from_run, rq2_from_run, rq3_from_run, rq4_from_run, rq5_from_run, rq6_from_run, rq7_observations
from evidence_contract import EvidenceClass
from phase4_metrics import ANALYSIS_VERSION, MetricResult
from phase4_metrics import analyze_rq1, analyze_rq2, analyze_rq3, analyze_rq4, analyze_rq5, analyze_rq6, analyze_rq7


def serialize_metrics(*, rq_code: str, metrics: Mapping[str, MetricResult], source_units: Iterable[ExperimentalUnit]) -> list[dict[str, object]]:
    unit_ids = sorted(str(unit.id) for unit in source_units)
    rows: list[dict[str, object]] = []
    for key, metric in metrics.items():
        value = metric.serialize()
        rows.append({
            "rq": rq_code, "judge": metric.judge, "condition": metric.condition,
            "metric": value["metric_name"], "value": value["value"],
            "numerator": value["numerator"], "denominator": value["denominator"],
            "eligible_n": value["eligible_n"], "analyzed_n": value["analyzed_n"],
            "ties": value["tie_count"], "unknowns": value["unknown_count"],
            "failures": value["failure_count"], "refusals": value["refusal_count"], "excluded": value["excluded_count"],
            "ci_low": value["ci_low"], "ci_high": value["ci_high"], "status": value["status"],
            "analysis_version": value["metric_version"], "evidence_class": EvidenceClass.CONTROLLED.value,
            "metric_key": key, "source_unit_ids": unit_ids,
        })
    return rows


def publish_analysis_run(*, session: Session, experiment: Experiment, manifest: ExperimentManifest, rq_code: str, metrics: Mapping[str, MetricResult], source_units: Iterable[ExperimentalUnit], analysis_seed: int) -> AnalysisRun:
    """Persist provenance and metrics atomically; accepts no legacy evidence."""
    if manifest.experiment_id != experiment.id:
        raise ValueError("analysis manifest does not belong to experiment")
    units = list(source_units)
    if any(unit.experiment_id != experiment.id or unit.manifest_id != manifest.id for unit in units):
        raise ValueError("analysis source units are outside the frozen experiment/manifest")
    payload = {
        "evidence_class": EvidenceClass.CONTROLLED.value,
        "dataset_version_id": str(experiment.dataset_version_id),
        "experiment_id": str(experiment.id), "manifest_id": str(manifest.id),
        "rq_code": rq_code, "protocol_version": manifest.protocol_version,
        "analysis_version": ANALYSIS_VERSION, "analysis_seed": analysis_seed,
        "source_unit_ids": sorted(str(unit.id) for unit in units),
        "results": serialize_metrics(rq_code=rq_code, metrics=metrics, source_units=units),
    }
    row = AnalysisRun(experiment_id=experiment.id, manifest_id=manifest.id, rq_code=rq_code, analysis_version=ANALYSIS_VERSION, analysis_seed=analysis_seed, status="COMPLETED", result_json=payload)
    session.add(row); session.flush()
    return row


def publish_manifest_analysis(*, session: Session, experiment: Experiment, manifest: ExperimentManifest, analysis_seed: int = 20260818, iterations: int = 10_000) -> AnalysisRun:
    """One non-ad-hoc persisted CONTROLLED evidence → AnalysisRun path for RQ1--7."""
    units = list(session.query(ExperimentalUnit).filter(ExperimentalUnit.manifest_id == manifest.id).all())
    runs = [run for run in session.query(ControlledRun).filter(ControlledRun.experimental_unit_id.in_([unit.id for unit in units])).all()
            if (run.metadata_json or {}).get("evidence_class") == EvidenceClass.CONTROLLED.value]
    by_unit = {run.experimental_unit_id: run for run in runs}
    pairs = [(by_unit[unit.id], unit) for unit in units if unit.id in by_unit]
    rq = manifest.rq_code
    if rq == "RQ1": metrics = analyze_rq1([rq1_from_run(run, unit) for run, unit in pairs], seed=analysis_seed, iterations=iterations)
    elif rq == "RQ2": metrics = analyze_rq2([rq2_from_run(run, unit, seed_policy="provider-recorded") for run, unit in pairs], seed=analysis_seed, iterations=iterations)
    elif rq == "RQ3": metrics = analyze_rq3([rq3_from_run(run, unit) for run, unit in pairs], seed=analysis_seed, iterations=iterations)
    elif rq == "RQ4": metrics = analyze_rq4([rq4_from_run(run, unit) for run, unit in pairs], seed=analysis_seed, iterations=iterations)
    elif rq == "RQ5": metrics = analyze_rq5([rq5_from_run(run, unit) for run, unit in pairs], seed=analysis_seed, iterations=iterations)
    elif rq == "RQ6": metrics = analyze_rq6([rq6_from_run(run, unit) for run, unit in pairs], seed=analysis_seed, iterations=iterations)
    elif rq == "RQ7": metrics = analyze_rq7(rq7_observations(pairs), seed=analysis_seed, iterations=iterations)
    else: raise ValueError(f"unsupported controlled research question {rq}")
    return publish_analysis_run(session=session, experiment=experiment, manifest=manifest, rq_code=rq, metrics=metrics, source_units=units, analysis_seed=analysis_seed)
