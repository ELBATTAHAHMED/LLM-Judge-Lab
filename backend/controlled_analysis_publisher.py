"""Persist the only API-consumable representation of controlled metrics."""
from __future__ import annotations

from typing import Iterable, Mapping

from sqlalchemy.orm import Session

from controlled_models import AnalysisRun, Experiment, ExperimentManifest, ExperimentalUnit
from evidence_contract import EvidenceClass
from phase4_metrics import ANALYSIS_VERSION, MetricResult


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
            "failures": value["failure_count"], "excluded": value["excluded_count"],
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
