"""Narrow execution and provider-free analysis support for the new RQ6 lineage.

The module deliberately has no top-level provider transport and never promotes
results into the frozen RQ1--RQ7 final-evidence API.  The only writing path is
called by the separately authorized manual execution command.
"""
from __future__ import annotations

import hashlib
import json
import random
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from controlled_analysis_metrics import MetricResult, bootstrap_ci
from controlled_evaluation import EvaluationRequest
from controlled_models import AnalysisRun, ControlledRun, DatasetVersion, Experiment, ExperimentalCondition, ExperimentManifest, ExperimentalUnit, PassAttempt, RunPass
from controlled_persistence import ControlledPersistence, to_json_safe
from controlled_prompt import PROMPT_TEMPLATE_VERSION, prompt_hash
from controlled_real_execution import BudgetLedger, ControlledRealRunner, ExecutionCaps, RealExecutionProfile
from evidence_contract import EvidenceClass
from execution_policy import FAILURE_POLICY_VERSION, RETRY_POLICY_VERSION
from experiment_planning import SOURCE_FAMILIES
from model_registry import MODEL_REGISTRY, Provider, get_model_spec
from models import Answer, Prompt
from pricing import CONFIG as PRICING_CONFIG
from routing_policy import frozen_openrouter_route, routing_fingerprint, routing_policy_version


ROOT = Path(__file__).resolve().parent.parent
RQ6_EVIDENCE_MANIFEST_PATH = ROOT / "evidence" / "final" / "rq6_counterbalanced" / "selection_manifest.json"
DESIGN_IDENTITY = "counterbalanced-source-family-v1"
ANALYSIS_IDENTITY = "counterbalanced-source-family-analysis-v1"
EXPECTED_MANIFEST_SHA256 = "27ec2c49ee8129802bd924e96734b4efb03249e506e7fbd9968977575b42c5cc"
EXECUTION_NAME = "rq6-counterbalanced-source-family-v1"
CONDITION_CODE = "COUNTERBALANCED_SOURCE_FAMILY"
ALLOWED_JUDGES = (
    "gpt-4o-mini",
    "anthropic/claude-3-haiku",
    "meta-llama/llama-3.3-70b-instruct",
)
HARD_CAP_USD = Decimal("0.46")
PLANNED_UNITS = 480
PLANNED_PASSES = 960
MAX_PROVIDER_ATTEMPTS = 1_152
MAX_INPUT_TOKENS = 834_377
MAX_OUTPUT_TOKENS = 403_200
SEED = 20260818
ITERATIONS = 10_000


def _sha256_manifest_body(manifest: Mapping[str, Any]) -> str:
    body = dict(manifest)
    body.pop("manifest_sha256", None)
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def load_preflight_manifest(path: Path = RQ6_EVIDENCE_MANIFEST_PATH) -> dict[str, Any]:
    material = json.loads(path.read_text(encoding="utf-8"))
    if material.get("manifest_sha256") != EXPECTED_MANIFEST_SHA256:
        raise ValueError("RQ6 preflight manifest SHA-256 does not match the authorized design")
    if _sha256_manifest_body(material) != EXPECTED_MANIFEST_SHA256:
        raise ValueError("RQ6 preflight manifest content does not match its persisted SHA-256")
    return material


def _family(value: str | None) -> str | None:
    return value.lower().replace("_", "-") if isinstance(value, str) and value else None


def validate_preflight_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Independently validate the persisted selection before DB writes/calls."""
    errors: list[str] = []
    units = list(manifest.get("units") or [])
    if manifest.get("design_identity") != DESIGN_IDENTITY:
        errors.append("wrong_design_identity")
    if manifest.get("analysis_identity") != ANALYSIS_IDENTITY:
        errors.append("wrong_analysis_identity")
    if manifest.get("source_identity_blinded_to_judge") is not True:
        errors.append("source_identity_not_blinded")
    if len(units) != PLANNED_UNITS:
        errors.append("wrong_unit_count")
    if len({row.get("unit_id") for row in units}) != len(units):
        errors.append("duplicate_preflight_unit_id")
    presentation = Counter()
    human = Counter()
    by_judge = Counter()
    pair_judges: set[tuple[int, str]] = set()
    for row in units:
        judge = row.get("judge_name")
        original = list(row.get("original_answer_ids") or [])
        source_mapping = row.get("source_family_mapping") or {}
        schedule = sorted(row.get("passes") or [], key=lambda item: item.get("pass_number", 0))
        if judge not in ALLOWED_JUDGES:
            errors.append(f"unsupported_or_excluded_judge:{judge}")
            continue
        by_judge[judge] += 1
        if len(original) != 2 or original[0] == original[1]:
            errors.append(f"invalid_original_answer_ids:{row.get('unit_id')}")
            continue
        if set(source_mapping) != {str(original[0]), str(original[1])}:
            errors.append(f"invalid_source_mapping:{row.get('unit_id')}")
            continue
        judge_family = _family(row.get("judge_family"))
        families = [_family(source_mapping[str(answer_id)]) for answer_id in original]
        if families.count(judge_family) != 1 or any(family is None for family in families):
            errors.append(f"invalid_same_family_comparison:{row.get('unit_id')}")
        if len(schedule) != 2 or [item.get("presentation_order") for item in schedule] != ["AB", "BA"]:
            errors.append(f"missing_ab_ba_schedule:{row.get('unit_id')}")
            continue
        if (schedule[0].get("presented_answer_a_id"), schedule[0].get("presented_answer_b_id")) != tuple(original):
            errors.append(f"invalid_ab_mapping:{row.get('unit_id')}")
        if (schedule[1].get("presented_answer_a_id"), schedule[1].get("presented_answer_b_id")) != tuple(reversed(original)):
            errors.append(f"invalid_ba_mapping:{row.get('unit_id')}")
        same = row.get("same_family_answer_id")
        presentation["A" if schedule[0].get("presented_answer_a_id") == same else "B" if schedule[0].get("presented_answer_b_id") == same else "MISSING"] += 1
        presentation["A" if schedule[1].get("presented_answer_a_id") == same else "B" if schedule[1].get("presented_answer_b_id") == same else "MISSING"] += 1
        human[(judge, row.get("human_reference_stratum"))] += 1
        pair_key = (int(row.get("preference_id")), judge)
        if pair_key in pair_judges:
            errors.append(f"duplicate_pair_judge:{row.get('unit_id')}")
        pair_judges.add(pair_key)
    if presentation["A"] != PLANNED_UNITS or presentation["B"] != PLANNED_UNITS or presentation["MISSING"]:
        errors.append("presentation_not_exactly_counterbalanced")
    for judge in ALLOWED_JUDGES:
        if human[(judge, "HUMAN_PREFERS_SAME_FAMILY")] != human[(judge, "HUMAN_PREFERS_OTHER_FAMILY")]:
            errors.append(f"human_reference_unbalanced:{judge}")
    expected_by_judge = {"gpt-4o-mini": 236, "anthropic/claude-3-haiku": 164, "meta-llama/llama-3.3-70b-instruct": 80}
    if dict(by_judge) != expected_by_judge:
        errors.append("unexpected_judge_allocation")
    return {
        "ok": not errors,
        "errors": sorted(set(errors)),
        "units": len(units),
        "passes": len(units) * 2,
        "same_family_slot_a": presentation["A"],
        "same_family_slot_b": presentation["B"],
        "human_reference_balance": {judge: {"same": human[(judge, "HUMAN_PREFERS_SAME_FAMILY")], "other": human[(judge, "HUMAN_PREFERS_OTHER_FAMILY")]} for judge in ALLOWED_JUDGES},
        "per_judge_units": dict(by_judge),
    }


def preexecution_checks(session: Session, manifest: Mapping[str, Any]) -> dict[str, Any]:
    validation = validate_preflight_manifest(manifest)
    errors = list(validation["errors"])
    datasets = list(session.scalars(select(DatasetVersion).where(DatasetVersion.source_checksum == manifest.get("dataset_checksum"))).all())
    if len(datasets) != 1 or datasets[0].version != manifest.get("dataset_snapshot_id"):
        errors.append("canonical_dataset_version_missing_or_ambiguous")
    for judge in ALLOWED_JUDGES:
        try:
            spec = get_model_spec(judge)
            if spec.provider is Provider.OPENROUTER:
                frozen_openrouter_route(judge)
        except Exception as exc:
            errors.append(f"invalid_routing_or_model:{judge}:{type(exc).__name__}")
    if manifest.get("prompt_template_version") != PROMPT_TEMPLATE_VERSION or manifest.get("prompt_template_sha256") != prompt_hash():
        errors.append("prompt_identity_mismatch")
    if manifest.get("routing_policy_version") != routing_policy_version() or manifest.get("routing_fingerprint") != routing_fingerprint():
        errors.append("routing_identity_mismatch")
    if PRICING_CONFIG.get("version") != manifest.get("cost_preflight", {}).get("pricing_version"):
        errors.append("pricing_identity_mismatch")
    if Decimal(str(manifest.get("cost_preflight", {}).get("recommended_hard_cap_usd", "0"))) != HARD_CAP_USD:
        errors.append("hard_cap_mismatch")
    prompt_ids = {row["prompt_id"] for row in manifest["units"]}
    answer_ids = {answer_id for row in manifest["units"] for answer_id in row["original_answer_ids"]}
    prompts = {row.id: row for row in session.scalars(select(Prompt).where(Prompt.id.in_(prompt_ids))).all()}
    answers = {row.id: row for row in session.scalars(select(Answer).where(Answer.id.in_(answer_ids))).all()}
    if len(prompts) != len(prompt_ids) or len(answers) != len(answer_ids):
        errors.append("canonical_prompt_or_answer_missing")
    else:
        for unit in manifest["units"]:
            prompt = prompts[unit["prompt_id"]]
            answer_a, answer_b = (answers[value] for value in unit["original_answer_ids"])
            if not prompt.text or not answer_a.text or not answer_b.text:
                errors.append("canonical_prompt_or_answer_empty")
                break
            if answer_a.prompt_id != prompt.id or answer_b.prompt_id != prompt.id:
                errors.append("answer_prompt_identity_mismatch")
                break
            source_mapping = unit["source_family_mapping"]
            if SOURCE_FAMILIES.get(answer_a.model_name) != source_mapping[str(answer_a.id)] or SOURCE_FAMILIES.get(answer_b.model_name) != source_mapping[str(answer_b.id)]:
                errors.append("stored_source_family_mapping_mismatch")
                break
    existing_manifest = _manifest_row(session)
    existing_old_rq6_manifests = list(session.scalars(select(ExperimentManifest).where(ExperimentManifest.rq_code == "RQ6", ExperimentManifest.manifest_sha256 != EXPECTED_MANIFEST_SHA256)).all())
    if existing_manifest is not None:
        existing_experiment = session.get(Experiment, existing_manifest.experiment_id)
        if existing_experiment is None or existing_experiment.experiment_name != EXECUTION_NAME:
            errors.append("existing_manifest_lineage_mismatch")
        existing_units = list(session.scalars(select(ExperimentalUnit).where(ExperimentalUnit.manifest_id == existing_manifest.id)).all())
        if existing_units:
            run_ids = list(session.scalars(select(ControlledRun.id).where(ControlledRun.experimental_unit_id.in_([unit.id for unit in existing_units]))).all())
            foreign_runs = list(session.scalars(select(ControlledRun).where(ControlledRun.id.in_(run_ids))).all()) if run_ids else []
            if any((run.metadata_json or {}).get("evidence_class") != EvidenceClass.CONTROLLED.value for run in foreign_runs):
                errors.append("pilot_or_superseded_contamination")
    return {**validation, "ok": not errors, "errors": sorted(set(errors)), "dataset_version_id": str(datasets[0].id) if len(datasets) == 1 else None, "existing_frozen_rq6_manifests_ignored": len(existing_old_rq6_manifests), "lineage_materialized": existing_manifest is not None, "spend_guard": {"max_usd": str(HARD_CAP_USD), "max_scientific_passes": PLANNED_PASSES, "max_provider_attempts": MAX_PROVIDER_ATTEMPTS, "max_input_tokens": MAX_INPUT_TOKENS, "max_output_tokens": MAX_OUTPUT_TOKENS}}


def _experiment(session: Session) -> Experiment | None:
    rows = list(session.scalars(select(Experiment).where(Experiment.experiment_name == EXECUTION_NAME)).all())
    if len(rows) > 1:
        raise ValueError("ambiguous counterbalanced RQ6 experiment lineage")
    return rows[0] if rows else None


def _manifest_row(session: Session) -> ExperimentManifest | None:
    rows = list(session.scalars(select(ExperimentManifest).where(ExperimentManifest.manifest_sha256 == EXPECTED_MANIFEST_SHA256)).all())
    if len(rows) > 1:
        raise ValueError("ambiguous counterbalanced RQ6 manifest lineage")
    return rows[0] if rows else None


def materialize_lineage(session: Session, manifest: Mapping[str, Any]) -> tuple[Experiment, ExperimentManifest, list[ExperimentalUnit]]:
    """Create/reuse only the new RQ6 experiment rows, never frozen evidence."""
    checks = preexecution_checks(session, manifest)
    if not checks["ok"]:
        raise ValueError("RQ6 execution preflight failed: " + ", ".join(checks["errors"]))
    dataset = session.get(DatasetVersion, checks["dataset_version_id"])
    if dataset is None:
        raise ValueError("canonical dataset disappeared during preflight")
    repo = ControlledPersistence(session)
    experiment = _experiment(session)
    if experiment is None:
        experiment = repo.create_experiment(
            dataset_version=dataset,
            experiment_name=EXECUTION_NAME,
            research_question=manifest["scientific_question"],
            hypothesis="Counterbalanced matched source-family preference association; no causal self-preference claim.",
            mitigation_strategy="NONE",
            analysis_version=ANALYSIS_IDENTITY,
            description="Separate RQ6 remediation lineage; it does not replace frozen Phase 11 RQ6 evidence.",
            metadata_json={"evidence_class": EvidenceClass.CONTROLLED.value, "design_identity": DESIGN_IDENTITY, "promote_to_final_api": False},
        )
    if str(experiment.dataset_version_id) != str(dataset.id):
        raise ValueError("existing RQ6 remediation experiment points at a different dataset")
    manifest_row = _manifest_row(session)
    if manifest_row is None:
        manifest_row = repo.create_manifest(experiment=experiment, rq_code="RQ6", protocol_version=DESIGN_IDENTITY, analysis_version=ANALYSIS_IDENTITY, dataset_snapshot_id=manifest["dataset_snapshot_id"], dataset_checksum=manifest["dataset_checksum"], manifest_sha256=manifest["manifest_sha256"], manifest_json=dict(manifest))
    if manifest_row.experiment_id != experiment.id or manifest_row.manifest_json.get("design_identity") != DESIGN_IDENTITY:
        raise ValueError("existing manifest does not belong to the new RQ6 lineage")
    condition = session.scalar(select(ExperimentalCondition).where(
        ExperimentalCondition.experiment_id == experiment.id,
        ExperimentalCondition.condition_code == CONDITION_CODE,
    ))
    if condition is None:
        condition = repo.create_condition(experiment=experiment, condition_code=CONDITION_CODE, label="Counterbalanced matched source-family preference", condition_json={"design_identity": DESIGN_IDENTITY, "presentation": "AB_BA", "source_identity_blinded_to_judge": True, "balance_proof": manifest["validation"]}, protocol_version=DESIGN_IDENTITY, prompt_template_version=PROMPT_TEMPLATE_VERSION)
    units: list[ExperimentalUnit] = []
    for row in manifest["units"]:
        answer_ids = row["original_answer_ids"]
        prompt, answer_a, answer_b = session.get(Prompt, row["prompt_id"]), session.get(Answer, answer_ids[0]), session.get(Answer, answer_ids[1])
        if prompt is None or answer_a is None or answer_b is None or not prompt.text or not answer_a.text or not answer_b.text:
            raise ValueError(f"missing canonical source record for planned unit {row['unit_id']}")
        source_mapping = row["source_family_mapping"]
        if SOURCE_FAMILIES.get(answer_a.model_name) != source_mapping[str(answer_a.id)] or SOURCE_FAMILIES.get(answer_b.model_name) != source_mapping[str(answer_b.id)]:
            raise ValueError(f"stored answer source metadata mismatch for planned unit {row['unit_id']}")
        spec = get_model_spec(row["judge_name"])
        units.append(repo.register_unit(experiment=experiment, manifest=manifest_row, condition=condition, prompt_id=prompt.id, answer_a_id=answer_a.id, answer_b_id=answer_b.id, prompt_category=row["category"], judge_model=spec.judge_name, provider=spec.provider.value, provider_model=spec.requested_model, prompt_template_version=PROMPT_TEMPLATE_VERSION, presentation_order="AB_BA", repetition_index=0, randomization_block=f"{row['other_family']}|{row['category']}", data_split="counterbalanced-rq6-v1", inclusion_status="INCLUDED", temperature=Decimal("0"), top_p=Decimal("1"), seed=SEED if spec.supports_seed else None, answer_a_author_id=answer_a.model_name, answer_b_author_id=answer_b.model_name, human_label=row["human_reference_label"], pairing_key=row["unit_id"]))
    if len({unit.id for unit in units}) != PLANNED_UNITS:
        raise ValueError("new RQ6 lineage did not materialize exactly 480 unique units")
    return experiment, manifest_row, units


def materialize_request(session: Session, unit: ExperimentalUnit) -> EvaluationRequest:
    if unit.judge_model not in ALLOWED_JUDGES or unit.presentation_order != "AB_BA":
        raise ValueError("unit is outside the counterbalanced RQ6 execution scope")
    prompt, answer_a, answer_b = session.get(Prompt, unit.prompt_id), session.get(Answer, unit.answer_a_id), session.get(Answer, unit.answer_b_id)
    if prompt is None or answer_a is None or answer_b is None or not prompt.text or not answer_a.text or not answer_b.text:
        raise ValueError(f"missing text for counterbalanced RQ6 unit {unit.id}")
    spec = get_model_spec(unit.judge_model)
    return EvaluationRequest(question=prompt.text, answer_a=answer_a.text, answer_b=answer_b.text, judge_name=unit.judge_model, provider=spec.provider, requested_model=spec.requested_model, temperature=float(unit.temperature or 0), top_p=float(unit.top_p or 1), seed=unit.seed if spec.supports_seed else None, prompt_template_version=PROMPT_TEMPLATE_VERSION, experiment_id=unit.experiment_id, controlled_unit_id=unit.id, repetition_index=unit.repetition_index, pass_number=1, original_answer_a_id=unit.answer_a_id, original_answer_b_id=unit.answer_b_id, presented_answer_a_id=unit.answer_a_id, presented_answer_b_id=unit.answer_b_id, presentation_provenance={"design_identity": DESIGN_IDENTITY, "logical_unit_id": unit.pairing_key, "pass_schedule": [{"pass_number": 1, "presentation_order": "AB"}, {"pass_number": 2, "presentation_order": "BA"}], "source_identity_blinded_to_judge": True})


def idempotency_key(unit: ExperimentalUnit) -> str:
    return hashlib.sha256(f"{DESIGN_IDENTITY}:{EXPECTED_MANIFEST_SHA256}:{unit.pairing_key}:dual".encode("utf-8")).hexdigest()


def _source_commit_and_tag() -> tuple[str, str]:
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        tag = subprocess.check_output(["git", "describe", "--tags", "--exact-match", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception as exc:
        raise PermissionError("RQ6 execution requires an exact immutable source tag at HEAD") from exc
    return commit, tag


def build_execution_profile(*, experiment: Experiment, manifest_row: ExperimentManifest, authorization_token: str) -> RealExecutionProfile:
    commit, tag = _source_commit_and_tag()
    upstreams = tuple(sorted(frozen_openrouter_route(judge)["upstream_provider"] for judge in ALLOWED_JUDGES if get_model_spec(judge).provider is Provider.OPENROUTER))
    return RealExecutionProfile(execution_mode="REAL", authorization_token=authorization_token, dataset_version_id=str(experiment.dataset_version_id), manifest_ids=(str(manifest_row.id),), manifest_hashes=(EXPECTED_MANIFEST_SHA256,), source_commit=commit, source_tag=tag, pricing_version=PRICING_CONFIG["version"], routing_version=routing_policy_version(), routing_fingerprint=routing_fingerprint(), prompt_version=PROMPT_TEMPLATE_VERSION, prompt_sha256=prompt_hash(), retry_policy_version=RETRY_POLICY_VERSION, failure_policy_version=FAILURE_POLICY_VERSION, analysis_version=ANALYSIS_IDENTITY, model_ids=ALLOWED_JUDGES, configured_upstreams=upstreams, caps=ExecutionCaps(PLANNED_PASSES, MAX_PROVIDER_ATTEMPTS, MAX_INPUT_TOKENS, MAX_OUTPUT_TOKENS, HARD_CAP_USD), evidence_class=EvidenceClass.CONTROLLED.value)


def restored_ledger(session: Session, *, profile: RealExecutionProfile, unit_ids: Iterable[Any]) -> BudgetLedger:
    """Restore reservations from the durable attempt ledger across resumes."""
    ids = list(unit_ids)
    run_ids = list(session.scalars(select(ControlledRun.id).where(ControlledRun.experimental_unit_id.in_(ids))).all()) if ids else []
    attempts = list(session.scalars(select(PassAttempt).where(PassAttempt.run_id.in_(run_ids))).all()) if run_ids else []
    ledger = BudgetLedger(profile)
    for attempt in attempts:
        if attempt.estimated_usd is None:
            continue  # blocked-before-transport attempts reserve no spend.
        ledger.scientific_passes.add((str(attempt.run_id), attempt.pass_number))
        ledger.provider_attempts += 1
        ledger.reserved_input_tokens += int((attempt.details_json or {}).get("estimated_input_tokens", 0))
        ledger.reserved_output_tokens += int((attempt.details_json or {}).get("estimated_output_tokens", 0))
        ledger.reserved_usd += Decimal(str(attempt.estimated_usd))
    if ledger.provider_attempts > profile.caps.max_provider_attempts or ledger.reserved_input_tokens > profile.caps.max_input_tokens or ledger.reserved_output_tokens > profile.caps.max_output_tokens or ledger.reserved_usd > profile.caps.max_usd:
        raise PermissionError("persisted RQ6 execution spend already exceeds its hard cap")
    return ledger


def _runs_by_unit(session: Session, units: Sequence[ExperimentalUnit]) -> dict[Any, ControlledRun]:
    ids = [unit.id for unit in units]
    runs = list(session.scalars(select(ControlledRun).where(ControlledRun.experimental_unit_id.in_(ids))).all()) if ids else []
    bad = [run.id for run in runs if (run.metadata_json or {}).get("evidence_class") != EvidenceClass.CONTROLLED.value]
    if bad:
        raise ValueError("PILOT/SUPERSEDED/non-controlled contamination detected in new RQ6 lineage")
    if len({run.experimental_unit_id for run in runs}) != len(runs):
        raise ValueError("multiple runs found for one counterbalanced RQ6 unit")
    return {run.experimental_unit_id: run for run in runs}


def execution_status(session: Session, manifest: Mapping[str, Any]) -> dict[str, Any]:
    row = _manifest_row(session)
    if row is None:
        return {"lineage_materialized": False, "planned_units": PLANNED_UNITS, "planned_passes": PLANNED_PASSES, "completed_units": 0, "completed_passes": 0, "completed_valid_passes": 0, "terminal_failures": 0, "pending_units": PLANNED_UNITS, "attempts": 0, "current_spend_usd": "0", "analysis_ready": False}
    units = list(session.scalars(select(ExperimentalUnit).where(ExperimentalUnit.manifest_id == row.id)).all())
    if len(units) != PLANNED_UNITS:
        raise ValueError("materialized RQ6 lineage does not contain exactly 480 units")
    runs = _runs_by_unit(session, units)
    run_ids = [run.id for run in runs.values()]
    passes = list(session.scalars(select(RunPass).where(RunPass.run_id.in_(run_ids))).all()) if run_ids else []
    attempts = list(session.scalars(select(PassAttempt).where(PassAttempt.run_id.in_(run_ids))).all()) if run_ids else []
    duplicate_passes = len({(record.run_id, record.pass_number) for record in passes}) != len(passes)
    completed_units = sum(len(run.passes) == 2 for run in runs.values())
    terminal_failures = sum(any(pass_.outcome not in {"ANSWER_A", "ANSWER_B", "TIE", "UNKNOWN"} for pass_ in run.passes) for run in runs.values() if len(run.passes) == 2)
    spend = sum((attempt.actual_usd if attempt.actual_usd is not None else attempt.estimated_usd or Decimal("0")) for attempt in attempts)
    return {"lineage_materialized": True, "manifest_id": str(row.id), "planned_units": PLANNED_UNITS, "planned_passes": PLANNED_PASSES, "completed_units": completed_units, "completed_passes": len(passes), "completed_valid_passes": sum(record.outcome in {"ANSWER_A", "ANSWER_B", "TIE", "UNKNOWN"} for record in passes), "terminal_failures": terminal_failures, "pending_units": PLANNED_UNITS - completed_units, "attempts": len(attempts), "current_spend_usd": str(spend), "duplicate_passes": duplicate_passes, "analysis_ready": completed_units == PLANNED_UNITS and len(passes) == PLANNED_PASSES and not duplicate_passes}


def execute_authorized(session: Session, *, manifest: Mapping[str, Any], authorization_token: str) -> dict[str, Any]:
    """The only provider-bound path; callers must explicitly invoke it."""
    experiment, manifest_row, units = materialize_lineage(session, manifest)
    profile = build_execution_profile(experiment=experiment, manifest_row=manifest_row, authorization_token=authorization_token)
    profile.assert_authorized()
    # The immutable new lineage must be durable before any paid request is
    # eligible.  Later commits remain one completed logical unit at a time.
    session.commit()
    runs = _runs_by_unit(session, units)
    pending = [unit for unit in sorted(units, key=lambda value: value.pairing_key or "") if unit.id not in runs or len(runs[unit.id].passes) < 2]
    runner = ControlledRealRunner(profile=profile, ledger=restored_ledger(session, profile=profile, unit_ids=[unit.id for unit in units]))
    for unit in pending:
        runner.execute(session=session, unit=unit, request=materialize_request(session, unit), idempotency_key=idempotency_key(unit), dual_pass=True)
        session.commit()
    return execution_status(session, manifest)


@dataclass(frozen=True)
class CounterbalancedObservation:
    unit_id: str
    judge_name: str
    human_reference_stratum: str
    human_reference_label: str
    pass_ab: str | None
    pass_ba: str | None

    @property
    def stable(self) -> str | None:
        return self.pass_ab if self.pass_ab in {"SAME", "OTHER"} and self.pass_ab == self.pass_ba else None


def _mapped_outcome(record: RunPass | None, unit_spec: Mapping[str, Any]) -> str | None:
    if record is None:
        return None
    if record.outcome == "TIE":
        return "TIE"
    if record.outcome != "ANSWER_A" and record.outcome != "ANSWER_B":
        return record.outcome or "MISSING_PASS"
    winner = record.winner_answer_id
    if winner == unit_spec["same_family_answer_id"]:
        return "SAME"
    if winner == unit_spec["other_family_answer_id"]:
        return "OTHER"
    return "INVALID_RESPONSE"


def reconcile_and_observations(session: Session, manifest: Mapping[str, Any]) -> list[CounterbalancedObservation]:
    status = execution_status(session, manifest)
    if not status["analysis_ready"]:
        raise ValueError("RQ6 post-execution analysis requires 480 complete units, 960 unique passes, and zero pending units")
    row = _manifest_row(session)
    if row is None:
        raise ValueError("counterbalanced RQ6 lineage is not materialized")
    units = {unit.pairing_key: unit for unit in session.scalars(select(ExperimentalUnit).where(ExperimentalUnit.manifest_id == row.id)).all()}
    if set(units) != {item["unit_id"] for item in manifest["units"]}:
        raise ValueError("database units do not exactly match the frozen RQ6 preflight selection")
    specs = {item["unit_id"]: item for item in manifest["units"]}
    observations: list[CounterbalancedObservation] = []
    for unit_id, unit in units.items():
        records = {item.pass_number: item for item in session.scalars(select(RunPass).join(ControlledRun).where(ControlledRun.experimental_unit_id == unit.id)).all()}
        spec = specs[unit_id]
        if (records[1].presented_answer_a_id, records[1].presented_answer_b_id) != tuple(spec["original_answer_ids"]) or (records[2].presented_answer_a_id, records[2].presented_answer_b_id) != tuple(reversed(spec["original_answer_ids"])):
            raise ValueError(f"persisted AB/BA mapping mismatch for {unit_id}")
        observations.append(CounterbalancedObservation(unit_id, unit.judge_model, spec["human_reference_stratum"], spec["human_reference_label"], _mapped_outcome(records.get(1), spec), _mapped_outcome(records.get(2), spec)))
    return sorted(observations, key=lambda value: value.unit_id)


def _result(name: str, rows: Sequence[CounterbalancedObservation], predicate, *, eligible: int, seed: int, iterations: int, notes: str) -> MetricResult:
    if not rows:
        return MetricResult(name, None, None, None, eligible, 0, excluded_count=eligible, status="NO_DATA", notes=notes)
    numerator = sum(predicate(row) for row in rows)
    low, high = bootstrap_ci(rows, lambda sample: sum(predicate(row) for row in sample) / len(sample) if sample else None, seed=seed, iterations=iterations)
    labels = [value for row in rows for value in (row.pass_ab, row.pass_ba)]
    return MetricResult(name, numerator / len(rows), numerator, len(rows), eligible, len(rows), tie_count=labels.count("TIE"), unknown_count=labels.count("UNKNOWN"), invalid_count=labels.count("INVALID_RESPONSE"), failure_count=sum(label in {"API_ERROR", "TIMEOUT", "REFUSAL", "AMBIGUOUS"} for label in labels), missing_count=sum(label is None or label == "MISSING_PASS" for label in labels), ci_low=low, ci_high=high, notes=notes, analysis_seed=seed, bootstrap_iterations=iterations)


def _stratified_bootstrap_ci(rows: Sequence[CounterbalancedObservation], statistic, *, seed: int, iterations: int) -> tuple[float | None, float | None]:
    groups = {judge: [row for row in rows if row.judge_name == judge] for judge in ALLOWED_JUDGES}
    if any(not group for group in groups.values()) or iterations < 1:
        return None, None
    rng = random.Random(seed)
    values: list[float] = []
    for _ in range(iterations):
        sample = [group[rng.randrange(len(group))] for group in groups.values() for _ in group]
        value = statistic(sample)
        if value is not None:
            values.append(value)
    if not values:
        return None, None
    values.sort()
    return values[int(0.025 * (len(values) - 1))], values[int(0.975 * (len(values) - 1))]


def analyze_counterbalanced_observations(rows: Iterable[CounterbalancedObservation], *, seed: int = SEED, iterations: int = ITERATIONS) -> dict[str, MetricResult]:
    values = list(rows)
    stable = [row for row in values if row.stable in {"SAME", "OTHER"}]
    complete_decisive = [row for row in values if row.pass_ab in {"SAME", "OTHER"} and row.pass_ba in {"SAME", "OTHER"}]
    metrics = {
        "stable_same_family_preference": _result("rq6_counterbalanced_stable_same_family_preference", stable, lambda row: row.stable == "SAME", eligible=len(values), seed=seed, iterations=iterations, notes="Primary: stable same-family outcomes / valid stable decisive units."),
        "stable_other_family_preference": _result("rq6_counterbalanced_stable_other_family_preference", stable, lambda row: row.stable == "OTHER", eligible=len(values), seed=seed, iterations=iterations, notes="Stable other-family outcomes / valid stable decisive units."),
        "order_sensitive_disagreement": _result("rq6_counterbalanced_order_sensitive_disagreement", complete_decisive, lambda row: row.pass_ab != row.pass_ba, eligible=len(values), seed=seed, iterations=iterations, notes="Mapped-original AB/BA disagreement / complete decisive pairs."),
        "valid_stable_decisive_coverage": _result("rq6_counterbalanced_valid_stable_decisive_coverage", values, lambda row: row.stable in {"SAME", "OTHER"}, eligible=len(values), seed=seed, iterations=iterations, notes="Stable decisive units / all selected units."),
        "tie_or_abstention_rate": _result("rq6_counterbalanced_tie_or_abstention_rate", values, lambda row: row.pass_ab in {"TIE", "UNKNOWN"} or row.pass_ba in {"TIE", "UNKNOWN"}, eligible=len(values), seed=seed, iterations=iterations, notes="At least one tie or abstention pass / all selected units."),
    }
    agreements: dict[str, list[CounterbalancedObservation]] = {}
    for stratum in ("HUMAN_PREFERS_SAME_FAMILY", "HUMAN_PREFERS_OTHER_FAMILY"):
        selected = [row for row in stable if row.human_reference_stratum == stratum]
        agreements[stratum] = selected
        metrics[f"human_reference_agreement:{stratum}"] = _result(
            "rq6_counterbalanced_human_reference_agreement",
            selected,
            lambda row: row.stable == ("SAME" if row.human_reference_stratum == "HUMAN_PREFERS_SAME_FAMILY" else "OTHER"),
            eligible=sum(row.human_reference_stratum == stratum for row in values),
            seed=seed,
            iterations=iterations,
            notes="Stable mapped-original agreement with the canonical human preference reference label.",
        )
    same_metric, other_metric = metrics["human_reference_agreement:HUMAN_PREFERS_SAME_FAMILY"], metrics["human_reference_agreement:HUMAN_PREFERS_OTHER_FAMILY"]
    if same_metric.value is None or other_metric.value is None:
        metrics["human_reference_agreement_difference"] = MetricResult("rq6_counterbalanced_human_reference_agreement_difference", None, None, None, len(values), 0, status="NOT_ESTIMABLE", notes="Both human-reference strata require stable decisive outcomes.")
    else:
        def difference(sample: Sequence[CounterbalancedObservation]) -> float | None:
            by = defaultdict(list)
            for item in sample:
                if item.stable in {"SAME", "OTHER"}:
                    by[item.human_reference_stratum].append(item)
            rates = []
            for stratum in ("HUMAN_PREFERS_SAME_FAMILY", "HUMAN_PREFERS_OTHER_FAMILY"):
                values_ = by[stratum]
                if not values_:
                    return None
                expected = "SAME" if stratum == "HUMAN_PREFERS_SAME_FAMILY" else "OTHER"
                rates.append(sum(item.stable == expected for item in values_) / len(values_))
            return rates[0] - rates[1]
        low, high = bootstrap_ci(values, difference, seed=seed, iterations=iterations)
        metrics["human_reference_agreement_difference"] = MetricResult("rq6_counterbalanced_human_reference_agreement_difference", same_metric.value - other_metric.value, None, None, len(values), len(stable), ci_low=low, ci_high=high, notes="Human-reference agreement when the reference prefers same family minus when it prefers other family.", analysis_seed=seed, bootstrap_iterations=iterations)
    judge_rates = []
    for judge in ALLOWED_JUDGES:
        judge_rows = [row for row in values if row.judge_name == judge]
        judge_stable = [row for row in judge_rows if row.stable in {"SAME", "OTHER"}]
        metric = _result("rq6_counterbalanced_stable_same_family_preference", judge_stable, lambda row: row.stable == "SAME", eligible=len(judge_rows), seed=seed, iterations=iterations, notes="Judge-specific primary estimand.")
        metrics[f"judge:{judge}:stable_same_family_preference"] = metric
        if metric.value is not None:
            judge_rates.append(metric.value)
    if len(judge_rates) != len(ALLOWED_JUDGES):
        metrics["equal_weight_judge_macro_average"] = MetricResult("rq6_counterbalanced_equal_weight_judge_macro_average", None, None, None, len(values), len(stable), status="NOT_ESTIMABLE", notes="Every configured in-scope judge requires at least one stable decisive unit for an equal-weight macro-average.")
    else:
        def macro(sample: Sequence[CounterbalancedObservation]) -> float | None:
            rates = []
            for judge in ALLOWED_JUDGES:
                judge_stable = [row for row in sample if row.judge_name == judge and row.stable in {"SAME", "OTHER"}]
                if not judge_stable:
                    return None
                rates.append(sum(row.stable == "SAME" for row in judge_stable) / len(judge_stable))
            return mean(rates)
        low, high = _stratified_bootstrap_ci(values, macro, seed=seed, iterations=iterations)
        metrics["equal_weight_judge_macro_average"] = MetricResult("rq6_counterbalanced_equal_weight_judge_macro_average", mean(judge_rates), None, len(judge_rates), len(values), len(stable), ci_low=low, ci_high=high, notes="Equal-weight mean of the three judge-specific primary estimates; bootstrap resamples logical units within judge.", analysis_seed=seed, bootstrap_iterations=iterations)
    return metrics


def analysis_payload(session: Session, manifest: Mapping[str, Any]) -> dict[str, Any]:
    observations = reconcile_and_observations(session, manifest)
    metrics = analyze_counterbalanced_observations(observations)
    return {"design_identity": DESIGN_IDENTITY, "analysis_identity": ANALYSIS_IDENTITY, "manifest_sha256": EXPECTED_MANIFEST_SHA256, "provider_calls": 0, "scientific_interpretation": "Counterbalanced Matched Source-Family Preference Association. Presentation-position confounding is controlled; source/content-quality confounding remains.", "metrics": {key: value.serialize() for key, value in metrics.items()}}


def _published_result_rows(metrics: Mapping[str, MetricResult], units: Sequence[ExperimentalUnit]) -> list[dict[str, Any]]:
    source_unit_ids = sorted(str(unit.id) for unit in units)
    rows: list[dict[str, Any]] = []
    for key, metric in metrics.items():
        value = metric.serialize()
        judge = key.split(":", 2)[1] if key.startswith("judge:") else None
        rows.append({
            "rq": "RQ6", "judge": judge, "condition": CONDITION_CODE,
            "metric": value["metric_name"], "value": value["value"],
            "numerator": value["numerator"], "denominator": value["denominator"],
            "eligible_n": value["eligible_n"], "analyzed_n": value["analyzed_n"],
            "ties": value["tie_count"], "unknowns": value["unknown_count"],
            "failures": value["failure_count"], "refusals": value["refusal_count"],
            "excluded": value["excluded_count"], "ci_low": value["ci_low"],
            "ci_high": value["ci_high"], "status": value["status"],
            "analysis_version": ANALYSIS_IDENTITY,
            "evidence_class": EvidenceClass.CONTROLLED.value,
            "metric_key": key, "source_unit_ids": source_unit_ids,
        })
    return rows


def publish_counterbalanced_analysis(session: Session, manifest: Mapping[str, Any]) -> AnalysisRun:
    """Persist the new RQ6 analysis only after provider-free reconciliation."""
    checks = preexecution_checks(session, manifest)
    if not checks["ok"]:
        raise ValueError("counterbalanced RQ6 reconciliation failed: " + ", ".join(checks["errors"]))
    manifest_row = _manifest_row(session)
    if manifest_row is None:
        raise ValueError("counterbalanced RQ6 lineage is not materialized")
    experiment = session.get(Experiment, manifest_row.experiment_id)
    if experiment is None:
        raise ValueError("counterbalanced RQ6 experiment is missing")
    units = list(session.scalars(select(ExperimentalUnit).where(ExperimentalUnit.manifest_id == manifest_row.id)).all())
    observations = reconcile_and_observations(session, manifest)
    metrics = analyze_counterbalanced_observations(observations)
    existing = list(session.scalars(select(AnalysisRun).where(
        AnalysisRun.manifest_id == manifest_row.id,
        AnalysisRun.rq_code == "RQ6",
        AnalysisRun.analysis_version == ANALYSIS_IDENTITY,
    )).all())
    if len(existing) > 1:
        raise ValueError("multiple counterbalanced RQ6 AnalysisRuns exist; refusing ambiguous promotion")
    payload = {
        "evidence_class": EvidenceClass.CONTROLLED.value,
        "design_identity": DESIGN_IDENTITY,
        "analysis_identity": ANALYSIS_IDENTITY,
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "dataset_version_id": str(experiment.dataset_version_id),
        "experiment_id": str(experiment.id),
        "manifest_id": str(manifest_row.id),
        "rq_code": "RQ6",
        "analysis_seed": SEED,
        "bootstrap_iterations": ITERATIONS,
        "scientific_interpretation": "Counterbalanced Matched Source-Family Preference Association. Presentation-position confounding is controlled; source/content-quality confounding remains. This is not causal proof of self-bias.",
        "limitations": ["Conclusions apply to stable decisive units.", "Stable-decisive coverage is reported explicitly.", "Source/content-quality confounding remains."],
        "results": _published_result_rows(metrics, units),
    }
    if existing:
        current = existing[0]
        if current.status != "COMPLETED" or (current.result_json or {}).get("manifest_sha256") != EXPECTED_MANIFEST_SHA256 or (current.result_json or {}).get("results") != payload["results"]:
            raise ValueError("existing counterbalanced RQ6 AnalysisRun does not match the recomputed preregistered result")
        experiment.status = "COMPLETED"
        manifest_row.status = "FROZEN"
        return current
    row = AnalysisRun(experiment_id=experiment.id, manifest_id=manifest_row.id, rq_code="RQ6", analysis_version=ANALYSIS_IDENTITY, analysis_seed=SEED, status="COMPLETED", result_json=to_json_safe(payload))
    session.add(row)
    experiment.status = "COMPLETED"
    manifest_row.status = "FROZEN"
    session.flush()
    return row
