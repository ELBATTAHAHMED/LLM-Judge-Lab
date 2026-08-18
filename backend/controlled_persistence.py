"""Offline-only persistence boundary for future controlled experiments.

This module intentionally contains no provider client, no HTTP call, and no
legacy-table writes.  Future execution code must hand it already-observed
provider results; Phase 1 tests use synthetic values exclusively.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

# Register the legacy tables in the shared metadata before controlled mappings
# reference them.  This import has no side effects beyond ORM registration.
import models as _legacy_models  # noqa: F401
from controlled_models import (
    ControlledRun, DatasetVersion, Experiment, ExperimentalCondition,
    ExperimentManifest, ExperimentalUnit, RunPass, CounterfactualVariant, PassAttempt,
)


class EvidenceClass(str, Enum):
    LEGACY_EXPLORATORY = "LEGACY_EXPLORATORY"
    LIVE_SANDBOX = "LIVE_SANDBOX"
    CONTROLLED = "CONTROLLED"
    PLANNED = "PLANNED"


class Outcome(str, Enum):
    ANSWER_A = "ANSWER_A"
    ANSWER_B = "ANSWER_B"
    TIE = "TIE"
    UNKNOWN = "UNKNOWN"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    API_ERROR = "API_ERROR"
    TIMEOUT = "TIMEOUT"
    REFUSAL = "REFUSAL"


OUTCOME_TO_STORAGE = {
    Outcome.ANSWER_A: ("ANSWER_A", "PARSED"),
    Outcome.ANSWER_B: ("ANSWER_B", "PARSED"),
    Outcome.TIE: ("TIE", "PARSED"),
    Outcome.UNKNOWN: ("UNKNOWN", "MISSING_RESPONSE"),
    Outcome.INVALID_RESPONSE: ("ERROR", "INVALID"),
    Outcome.API_ERROR: ("ERROR", "PROVIDER_ERROR"),
    Outcome.TIMEOUT: ("ERROR", "TIMEOUT"),
    # ``passes.parse_status`` is constrained by the recovered v0003 schema;
    # refusal remains distinguished in the attempt ledger/error code.
    Outcome.REFUSAL: ("ERROR", "PROVIDER_ERROR"),
}


@dataclass(frozen=True)
class PassObservation:
    pass_number: int
    presented_answer_a_id: int
    presented_answer_b_id: int
    outcome: Outcome
    confidence: Decimal | None = None
    raw_provider_response: dict[str, Any] | None = None
    reasoning_summary: str | None = None
    api_response_id: str | None = None
    effective_model: str | None = None
    provider_model: str | None = None
    model_version: str | None = None
    latency_ms: int | None = None
    criteria_scores: dict[str, Any] | None = None
    explanation: str | None = None


def classify_legacy_prompt_category(category: str | None) -> EvidenceClass:
    """Classify legacy rows without changing them."""
    return EvidenceClass.LIVE_SANDBOX if category in {"live", "live_calibrated", "ensemble_eval"} else EvidenceClass.LEGACY_EXPLORATORY


def canonical_unit_fingerprint(*, experiment_id: uuid.UUID, manifest_id: uuid.UUID, condition_code: str, prompt_id: int, answer_a_id: int, answer_b_id: int, repetition_index: int, presentation_order: str, judge_model: str, provider: str, provider_model: str, prompt_template_version: str, temperature: Decimal | None, top_p: Decimal | None, seed: int | None, variant_checksum: str | None = None, dataset_checksum: str | None = None) -> str:
    """Identity includes every scientifically meaningful execution configuration."""
    material = "|".join(map(str, (experiment_id, manifest_id, dataset_checksum, condition_code, prompt_id, answer_a_id, answer_b_id, repetition_index, presentation_order, judge_model, provider, provider_model, prompt_template_version, temperature, top_p, seed, variant_checksum)))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class ControlledPersistence:
    """The only intended write path for future controlled evidence."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create_dataset_version(self, *, source_name: str, version: str | None, source_checksum: str | None, **kwargs: Any) -> DatasetVersion:
        existing = self.session.scalar(select(DatasetVersion).where(
            DatasetVersion.source_name == source_name,
            DatasetVersion.version == version,
            DatasetVersion.source_checksum == source_checksum,
        ))
        if existing is not None:
            return existing
        row = DatasetVersion(source_name=source_name, version=version, source_checksum=source_checksum, **kwargs)
        self.session.add(row)
        self.session.flush()
        return row

    def create_experiment(self, *, dataset_version: DatasetVersion, experiment_name: str, research_question: str, hypothesis: str, mitigation_strategy: str = "NONE", analysis_version: str | None = None, description: str | None = None, metadata_json: dict[str, Any] | None = None) -> Experiment:
        row = Experiment(dataset_version_id=dataset_version.id, experiment_name=experiment_name, research_question=research_question, hypothesis=hypothesis, mitigation_strategy=mitigation_strategy, analysis_version=analysis_version, description=description, status="PLANNED", metadata_json=metadata_json)
        self.session.add(row)
        self.session.flush()
        return row

    def create_condition(self, *, experiment: Experiment, condition_code: str, label: str, condition_json: dict[str, Any], protocol_version: str, prompt_template_version: str | None = None) -> ExperimentalCondition:
        row = ExperimentalCondition(experiment_id=experiment.id, condition_code=condition_code, label=label, condition_json=condition_json, protocol_version=protocol_version, prompt_template_version=prompt_template_version)
        self.session.add(row)
        self.session.flush()
        return row

    def create_manifest(self, *, experiment: Experiment, rq_code: str, protocol_version: str, analysis_version: str, dataset_snapshot_id: str, dataset_checksum: str, manifest_sha256: str, manifest_json: dict[str, Any]) -> ExperimentManifest:
        row = ExperimentManifest(experiment_id=experiment.id, rq_code=rq_code, protocol_version=protocol_version, analysis_version=analysis_version, dataset_snapshot_id=dataset_snapshot_id, dataset_checksum=dataset_checksum, manifest_sha256=manifest_sha256, manifest_json=manifest_json, status="PLANNED")
        self.session.add(row)
        self.session.flush()
        return row

    def register_unit(self, *, experiment: Experiment, manifest: ExperimentManifest, condition: ExperimentalCondition, prompt_id: int, answer_a_id: int, answer_b_id: int, prompt_category: str, judge_model: str, provider: str, provider_model: str, prompt_template_version: str, presentation_order: str, repetition_index: int, randomization_block: str, data_split: str, inclusion_status: str, temperature: Decimal | None = None, top_p: Decimal | None = None, seed: int | None = None, answer_a_author_id: str | None = None, answer_b_author_id: str | None = None, human_label: str | None = None, exclusion_reason: str | None = None, pairing_key: str | None = None, variant_checksum: str | None = None, counterfactual_variant: CounterfactualVariant | None = None) -> ExperimentalUnit:
        if experiment.id != manifest.experiment_id or experiment.id != condition.experiment_id:
            raise ValueError("manifest and condition must belong to the experiment")
        fingerprint = canonical_unit_fingerprint(experiment_id=experiment.id, manifest_id=manifest.id, dataset_checksum=manifest.dataset_checksum, condition_code=condition.condition_code, prompt_id=prompt_id, answer_a_id=answer_a_id, answer_b_id=answer_b_id, repetition_index=repetition_index, presentation_order=presentation_order, judge_model=judge_model, provider=provider, provider_model=provider_model, prompt_template_version=prompt_template_version, temperature=temperature, top_p=top_p, seed=seed, variant_checksum=variant_checksum)
        existing = self.session.scalar(select(ExperimentalUnit).where(ExperimentalUnit.unit_fingerprint == fingerprint))
        if existing is not None:
            return existing
        row = ExperimentalUnit(experiment_id=experiment.id, manifest_id=manifest.id, condition_id=condition.id, counterfactual_variant_id=counterfactual_variant.id if counterfactual_variant else None, prompt_id=prompt_id, answer_a_id=answer_a_id, answer_b_id=answer_b_id, answer_a_author_id=answer_a_author_id, answer_b_author_id=answer_b_author_id, human_label=human_label, prompt_category=prompt_category, condition_code=condition.condition_code, presentation_order=presentation_order, judge_model=judge_model, provider=provider, provider_model=provider_model, prompt_template_version=prompt_template_version, temperature=temperature, top_p=top_p, seed=seed, repetition_index=repetition_index, randomization_block=randomization_block, data_split=data_split, inclusion_status=inclusion_status, exclusion_reason=exclusion_reason, pairing_key=pairing_key, unit_fingerprint=fingerprint)
        self.session.add(row)
        self.session.flush()
        return row

    def get_or_create_variant(self, *, experiment: Experiment, original_answer_id: int, condition_code: str, transformation_method: str, transformation_version: str, original_checksum: str, variant_checksum: str, variant_text: str, original_word_count: int, variant_word_count: int, validation_status: str, validation_details: dict[str, Any]) -> CounterfactualVariant:
        existing = self.session.scalar(select(CounterfactualVariant).where(CounterfactualVariant.experiment_id == experiment.id, CounterfactualVariant.original_answer_id == original_answer_id, CounterfactualVariant.condition_code == condition_code, CounterfactualVariant.transformation_version == transformation_version, CounterfactualVariant.variant_checksum == variant_checksum))
        if existing is not None:
            if existing.variant_text != variant_text:
                raise ValueError("immutable variant checksum/text mismatch")
            return existing
        row = CounterfactualVariant(experiment_id=experiment.id, original_answer_id=original_answer_id, variant_answer_id=None, variant_text=variant_text, condition_code=condition_code, transformation_method=transformation_method, transformation_version=transformation_version, original_checksum=original_checksum, variant_checksum=variant_checksum, original_word_count=original_word_count, variant_word_count=variant_word_count, original_token_estimate=original_word_count, variant_token_estimate=variant_word_count, validation_status=validation_status, validation_details=validation_details)
        self.session.add(row); self.session.flush(); return row

    def create_run(self, *, unit: ExperimentalUnit, idempotency_key: str, requested_model: str, judge_name: str | None = None, provider: str | None = None, effective_model: str | None = None, model_version: str | None = None, run_kind: str = "STANDARD", metadata_json: dict[str, Any] | None = None) -> ControlledRun:
        existing = self.session.scalar(select(ControlledRun).where(ControlledRun.idempotency_key == idempotency_key))
        if existing is not None:
            return existing
        metadata = dict(metadata_json or {})
        metadata.update({"evidence_class": EvidenceClass.CONTROLLED.value, "controlled_unit_id": str(unit.id), "manifest_id": str(unit.manifest_id), "condition_code": unit.condition_code, "unit_fingerprint": unit.unit_fingerprint})
        row = ControlledRun(experimental_unit_id=unit.id, experiment_id=unit.experiment_id, prompt_id=unit.prompt_id, original_answer_a_id=unit.answer_a_id, original_answer_b_id=unit.answer_b_id, judge_name=judge_name or unit.judge_model, provider=provider or unit.provider, requested_model=requested_model, effective_model=effective_model, provider_model=unit.provider_model, model_version=model_version, prompt_template_version=unit.prompt_template_version, temperature=unit.temperature, top_p=unit.top_p, seed=unit.seed, repetition_index=unit.repetition_index, run_kind=run_kind, status="PENDING", idempotency_key=idempotency_key, metadata_json=metadata)
        self.session.add(row)
        self.session.flush()
        return row

    def mark_running(self, run: ControlledRun) -> ControlledRun:
        run.status = "RUNNING"
        run.started_at = datetime.now(timezone.utc)
        self.session.flush()
        return run

    def begin_attempt(self, *, run: ControlledRun, pass_number: int) -> PassAttempt:
        """Persist IN_PROGRESS before provider invocation; never overwrite history."""
        existing = list(self.session.scalars(select(PassAttempt).where(PassAttempt.run_id == run.id, PassAttempt.pass_number == pass_number).order_by(PassAttempt.attempt_index)).all())
        if any(row.state == "SUCCEEDED" for row in existing):
            return next(row for row in existing if row.state == "SUCCEEDED")
        if existing and existing[-1].state == "AMBIGUOUS":
            raise RuntimeError("AMBIGUOUS pass requires explicit operator resolution; automatic resend is forbidden")
        if existing and existing[-1].state == "IN_PROGRESS":
            raise RuntimeError("IN_PROGRESS pass is ambiguous after restart; explicit operator resolution is required")
        if existing and existing[-1].state == "FAILED_FINAL" and not ((existing[-1].details_json or {}).get("authorized_rerun") is True):
            raise RuntimeError("FAILED_FINAL pass cannot be resent without recorded AUTHORIZED_RERUN resolution")
        attempt_index = len(existing)
        material = f"{run.idempotency_key}|{pass_number}|{attempt_index}"
        row = PassAttempt(run_id=run.id, pass_number=pass_number, attempt_index=attempt_index, attempt_id=hashlib.sha256(material.encode()).hexdigest(), state="IN_PROGRESS")
        self.session.add(row); self.session.flush(); return row

    def finish_attempt(self, attempt: PassAttempt, *, state: str, failure_category: str | None = None, provider_response_id: str | None = None, details: dict[str, Any] | None = None) -> PassAttempt:
        if state not in {"SUCCEEDED", "FAILED_RETRYABLE", "FAILED_FINAL", "AMBIGUOUS"}:
            raise ValueError(f"invalid terminal attempt state {state}")
        if attempt.state != "IN_PROGRESS":
            raise ValueError(f"illegal attempt transition {attempt.state} -> {state}")
        if state == "SUCCEEDED":
            successful = self.session.scalar(select(PassAttempt).where(PassAttempt.run_id == attempt.run_id, PassAttempt.pass_number == attempt.pass_number, PassAttempt.state == "SUCCEEDED"))
            if successful is not None:
                raise ValueError("a scientific pass may have only one successful terminal attempt")
        attempt.state, attempt.failure_category, attempt.provider_response_id = state, failure_category, provider_response_id
        attempt.retry_decision = "RETRY" if state == "FAILED_RETRYABLE" else "OPERATOR_REVIEW" if state == "AMBIGUOUS" else "FINAL"
        attempt.completed_at, attempt.details_json = datetime.now(timezone.utc), details
        self.session.flush(); return attempt

    def resolve_ambiguous_attempt(self, *, attempt: PassAttempt, resolution: str, details: dict[str, Any] | None = None) -> PassAttempt:
        """Record an explicit operator decision without erasing paid-attempt history.

        RECOVERED_SUCCESS is allowed only after the result itself was durably
        persisted.  AUTHORIZED_RERUN turns the ambiguous record into a terminal
        audit record and authorizes exactly the next ledger attempt.
        """
        if attempt.state != "AMBIGUOUS":
            raise ValueError("only AMBIGUOUS attempts require operator resolution")
        if resolution not in {"RECOVERED_SUCCESS", "FAILED_FINAL", "AUTHORIZED_RERUN"}:
            raise ValueError("invalid ambiguity resolution")
        history = dict(attempt.details_json or {})
        history.update(details or {})
        history["operator_resolution"] = resolution
        if resolution == "RECOVERED_SUCCESS":
            persisted = self.session.scalar(select(RunPass).where(RunPass.run_id == attempt.run_id, RunPass.pass_number == attempt.pass_number))
            if persisted is None:
                raise ValueError("RECOVERED_SUCCESS requires an already persisted pass")
            attempt.state, attempt.retry_decision = "SUCCEEDED", "RECOVERED_SUCCESS"
        else:
            attempt.state, attempt.retry_decision = "FAILED_FINAL", resolution
            if resolution == "AUTHORIZED_RERUN": history["authorized_rerun"] = True
        attempt.details_json = history
        attempt.completed_at = datetime.now(timezone.utc)
        self.session.flush()
        return attempt

    def record_pass(self, *, run: ControlledRun, observation: PassObservation) -> RunPass:
        if observation.presented_answer_a_id == observation.presented_answer_b_id:
            raise ValueError("A/B presentation requires two distinct answers")
        raw_verdict, parse_status = OUTCOME_TO_STORAGE[observation.outcome]
        winner = observation.presented_answer_a_id if observation.outcome is Outcome.ANSWER_A else observation.presented_answer_b_id if observation.outcome is Outcome.ANSWER_B else None
        existing = self.session.scalar(select(RunPass).where(RunPass.run_id == run.id, RunPass.pass_number == observation.pass_number))
        if existing is not None:
            return existing
        row = RunPass(run_id=run.id, pass_number=observation.pass_number, presented_answer_a_id=observation.presented_answer_a_id, presented_answer_b_id=observation.presented_answer_b_id, raw_verdict=raw_verdict, winner_answer_id=winner, parse_status=parse_status, confidence=observation.confidence, raw_provider_response=observation.raw_provider_response, reasoning_summary=observation.reasoning_summary, api_response_id=observation.api_response_id, effective_model=observation.effective_model, provider_model=observation.provider_model, model_version=observation.model_version, latency_ms=observation.latency_ms, criteria_scores=observation.criteria_scores, explanation=observation.explanation)
        self.session.add(row)
        self.session.flush()
        return row

    def complete_run(self, *, run: ControlledRun, outcome: Outcome, latency_ms: int | None = None, api_response_id: str | None = None, error_code: str | None = None, error_details: str | None = None, retry_count: int = 0, final_explanation: str | None = None, final_criteria: dict[str, Any] | None = None, final_confidence: Decimal | None = None) -> ControlledRun:
        stored_result, parse_status = OUTCOME_TO_STORAGE[outcome]
        run.final_result_type = stored_result
        run.final_parse_status = parse_status
        run.final_winner_answer_id = run.original_answer_a_id if outcome is Outcome.ANSWER_A else run.original_answer_b_id if outcome is Outcome.ANSWER_B else None
        run.latency_ms = latency_ms
        run.api_response_id = api_response_id
        run.error_code = error_code
        run.error_details = error_details
        run.retry_count = retry_count
        run.final_explanation = final_explanation
        run.final_criteria = final_criteria
        run.final_confidence = final_confidence
        run.completed_at = datetime.now(timezone.utc)
        run.status = "SUCCEEDED" if outcome in {Outcome.ANSWER_A, Outcome.ANSWER_B, Outcome.TIE, Outcome.UNKNOWN} else "FAILED"
        self.session.flush()
        return run

    def complete_dual_run(self, *, run: ControlledRun, decision: str, outcome: Outcome | None, latency_ms: int, retry_count: int, final_explanation: str) -> ControlledRun:
        """Finalize a derived two-pass result without mislabeling disagreement."""
        schema_classification = {
            "CONSISTENT": "SAME_DECISIVE_WINNER",
            "DISAGREEMENT": "DECISIVE_FLIP",
            "CONSISTENT_TIE": "CONSISTENT_TIE",
            "CONSISTENT_UNKNOWN": "CONSISTENT_UNKNOWN",
            "PARTIAL_OR_NONDECISIVE": "PARTIAL_EXECUTION",
        }[decision]
        run.dual_pass_classification = schema_classification
        metadata = dict(run.metadata_json or {})
        # ``DECISIVE_FLIP`` is the recovered schema vocabulary, not a causal
        # position-bias claim.  Preserve the scientifically neutral derivation.
        metadata["derived_dual_pass_decision"] = decision
        run.metadata_json = metadata
        run.latency_ms = latency_ms
        run.retry_count = retry_count
        run.final_explanation = final_explanation
        run.completed_at = datetime.now(timezone.utc)
        if outcome is not None:
            stored_result, parse_status = OUTCOME_TO_STORAGE[outcome]
            run.final_result_type = stored_result
            run.final_parse_status = parse_status
            run.final_winner_answer_id = run.original_answer_a_id if outcome is Outcome.ANSWER_A else run.original_answer_b_id if outcome is Outcome.ANSWER_B else None
            run.status = "SUCCEEDED"
        else:
            run.final_result_type = "PARTIAL"
            run.final_parse_status = "MULTI_PASS_DISAGREEMENT" if decision == "DISAGREEMENT" else "PARTIAL_EXECUTION"
            run.final_winner_answer_id = None
            run.status = "PARTIAL"
        self.session.flush()
        return run

    def controlled_runs(self) -> list[ControlledRun]:
        """Return controlled evidence only; legacy/live evidence has no access path here."""
        return [run for run in self.session.scalars(select(ControlledRun)).all() if (run.metadata_json or {}).get("evidence_class") == EvidenceClass.CONTROLLED.value]
