"""One validated, provider-agnostic execution path for controlled evidence.

There is intentionally no live provider implementation in this module.  A
future provider adapter must implement ``evaluate`` and return an envelope; the
engine then validates and persists its response without ever using legacy
``judge_decisions``.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from time import perf_counter
from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, StrictInt, StrictStr, model_validator

from controlled_persistence import ControlledPersistence, Outcome, PassObservation
from controlled_prompt import PROMPT_TEMPLATE_VERSION
from execution_policy import next_backoff_seconds, retry_rule, terminal_state
from controlled_models import ControlledRun, ExperimentalUnit
from model_registry import Provider, get_model_spec


MAX_INPUT_CHARACTERS = 100_000
class EvaluationRequest(BaseModel):
    """Fully identified input to one presentation pass (not a retry policy)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: StrictStr = Field(min_length=1, max_length=MAX_INPUT_CHARACTERS)
    answer_a: StrictStr = Field(min_length=1, max_length=MAX_INPUT_CHARACTERS)
    answer_b: StrictStr = Field(min_length=1, max_length=MAX_INPUT_CHARACTERS)
    judge_name: StrictStr
    provider: Provider
    requested_model: StrictStr
    temperature: FiniteFloat = Field(ge=0, le=2)
    top_p: FiniteFloat = Field(ge=0, le=1)
    seed: StrictInt | None = None
    prompt_template_version: StrictStr = Field(min_length=1)
    experiment_id: UUID
    controlled_unit_id: UUID
    repetition_index: StrictInt = Field(ge=0)
    pass_number: StrictInt = Field(ge=1)
    original_answer_a_id: StrictInt = Field(gt=0)
    original_answer_b_id: StrictInt = Field(gt=0)
    presented_answer_a_id: StrictInt = Field(gt=0)
    presented_answer_b_id: StrictInt = Field(gt=0)
    retry_count: StrictInt = Field(default=0, ge=0)
    # RQ4/RQ5 record which physical slot carried a checksum-linked variant;
    # this is provenance, not a new scientific answer identity.
    presentation_provenance: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_identity_and_capabilities(self) -> "EvaluationRequest":
        if self.original_answer_a_id == self.original_answer_b_id or self.presented_answer_a_id == self.presented_answer_b_id:
            raise ValueError("Answer A and Answer B must be distinct identities")
        spec = get_model_spec(self.judge_name)
        if self.provider is not spec.provider or self.requested_model != spec.requested_model:
            raise ValueError("judge_name, provider, and requested_model must exactly match the model registry")
        if self.temperature != 0 and not spec.supports_temperature:
            raise ValueError(f"{self.judge_name} does not support temperature")
        if self.top_p != 1 and not spec.supports_top_p:
            raise ValueError(f"{self.judge_name} does not support top_p")
        if self.seed is not None and not spec.supports_seed:
            raise ValueError(f"{self.judge_name} seed_not_supported")
        return self


class CriterionScores(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    correctness: StrictInt = Field(ge=1, le=5)
    relevance: StrictInt = Field(ge=1, le=5)
    completeness: StrictInt = Field(ge=1, le=5)
    clarity: StrictInt = Field(ge=1, le=5)
    safety: StrictInt = Field(ge=1, le=5)


class ProviderJudgement(BaseModel):
    """Strict scientific judgement payload; confidence is self-reported only."""

    model_config = ConfigDict(extra="forbid", strict=True)
    verdict: Literal["ANSWER_A", "ANSWER_B", "TIE", "UNKNOWN"]
    criteria_scores: CriterionScores
    confidence: FiniteFloat = Field(ge=0, le=1)
    explanation: StrictStr = Field(min_length=1)


@dataclass(frozen=True)
class ProviderResponse:
    raw_response: Any
    effective_model: str | None = None
    model_version: str | None = None
    provider_response_id: str | None = None
    upstream_provider_model: str | None = None
    route_provenance: dict[str, Any] | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


class ProviderAdapter(Protocol):
    def evaluate(self, request: EvaluationRequest) -> ProviderResponse: ...


class ProviderCallError(RuntimeError):
    """Typed, provider-neutral transport/configuration failure."""
    def __init__(self, category: str, message: str = "") -> None:
        self.category = category
        super().__init__(message or category)


@dataclass(frozen=True)
class NormalizedEvaluationResult:
    outcome: Outcome
    criterion_scores: dict[str, int] | None
    confidence: Decimal | None  # self-reported judge confidence, never calibration
    explanation: str | None
    raw_response: Any
    effective_model: str
    model_version: str | None
    provider_response_id: str | None
    upstream_provider_model: str
    latency_ms: int
    parse_status: str
    error_code: str | None = None
    error_details: str | None = None
    route_provenance: dict[str, Any] | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


class ControlledEvaluationEngine:
    def __init__(self, adapter: ProviderAdapter) -> None:
        self.adapter = adapter

    def evaluate(self, request: EvaluationRequest) -> NormalizedEvaluationResult:
        # Pydantic constructed ``request`` before this call; no provider work can
        # occur until all local constraints have passed.
        started = perf_counter()
        try:
            response = self.adapter.evaluate(request)
        except TimeoutError as exc:
            return self._failure(Outcome.TIMEOUT, started, "TIMEOUT", str(exc))
        except ProviderCallError as exc:
            outcome = Outcome.REFUSAL if exc.category == "REFUSAL" else Outcome.API_ERROR
            return self._failure(outcome, started, exc.category, str(exc))
        except Exception as exc:  # unknown adapter failures remain terminal; policy never retries generic errors
            return self._failure(Outcome.API_ERROR, started, "PROVIDER_ERROR", str(exc))
        latency_ms = round((perf_counter() - started) * 1000)
        effective_model = response.effective_model or "NOT_RETURNED"
        upstream = response.upstream_provider_model or "NOT_RETURNED"
        try:
            judgement = ProviderJudgement.model_validate(response.raw_response)
        except Exception as exc:
            return NormalizedEvaluationResult(Outcome.INVALID_RESPONSE, None, None, None, response.raw_response, effective_model, response.model_version, response.provider_response_id, upstream, latency_ms, "INVALID", "INVALID_RESPONSE", str(exc), getattr(response, "route_provenance", None), getattr(response, "input_tokens", None), getattr(response, "output_tokens", None))
        return NormalizedEvaluationResult(
            Outcome(judgement.verdict), judgement.criteria_scores.model_dump(), Decimal(str(judgement.confidence)),
            judgement.explanation, response.raw_response, effective_model, response.model_version,
            response.provider_response_id, upstream, latency_ms, "PARSED", route_provenance=getattr(response, "route_provenance", None), input_tokens=getattr(response, "input_tokens", None), output_tokens=getattr(response, "output_tokens", None),
        )

    @staticmethod
    def _failure(outcome: Outcome, started: float, code: str, details: str) -> NormalizedEvaluationResult:
        return NormalizedEvaluationResult(outcome, None, None, None, None, "NOT_RETURNED", None, None, "NOT_RETURNED", round((perf_counter() - started) * 1000), OUTCOME_PARSE_STATUS[outcome], code, details)


OUTCOME_PARSE_STATUS = {
    Outcome.ANSWER_A: "PARSED", Outcome.ANSWER_B: "PARSED", Outcome.TIE: "PARSED", Outcome.UNKNOWN: "MISSING_RESPONSE",
    Outcome.INVALID_RESPONSE: "INVALID", Outcome.API_ERROR: "PROVIDER_ERROR", Outcome.TIMEOUT: "TIMEOUT", Outcome.REFUSAL: "REFUSAL",
}


@dataclass(frozen=True)
class DualPassDecision:
    classification: str
    final_outcome: Outcome | None
    mapped_winner_ids: tuple[int | None, int | None]


def mapped_original_winner(request: EvaluationRequest, result: NormalizedEvaluationResult) -> int | None:
    if result.outcome is Outcome.ANSWER_A:
        return request.presented_answer_a_id
    if result.outcome is Outcome.ANSWER_B:
        return request.presented_answer_b_id
    return None


def derive_dual_pass_decision(first_request: EvaluationRequest, first: NormalizedEvaluationResult, second_request: EvaluationRequest, second: NormalizedEvaluationResult) -> DualPassDecision:
    winners = (mapped_original_winner(first_request, first), mapped_original_winner(second_request, second))
    if winners[0] is not None and winners[0] == winners[1]:
        outcome = Outcome.ANSWER_A if winners[0] == first_request.original_answer_a_id else Outcome.ANSWER_B
        return DualPassDecision("CONSISTENT", outcome, winners)
    if winners[0] is not None and winners[1] is not None:
        return DualPassDecision("DISAGREEMENT", None, winners)
    if first.outcome is Outcome.TIE and second.outcome is Outcome.TIE:
        return DualPassDecision("CONSISTENT_TIE", Outcome.TIE, winners)
    if first.outcome is Outcome.UNKNOWN and second.outcome is Outcome.UNKNOWN:
        return DualPassDecision("CONSISTENT_UNKNOWN", Outcome.UNKNOWN, winners)
    return DualPassDecision("PARTIAL_OR_NONDECISIVE", None, winners)


class ControlledExecutionService:
    """Persists controlled passes; its only evaluator dependency is an adapter."""

    def __init__(self, persistence: ControlledPersistence, evaluator: ControlledEvaluationEngine, *, evidence_class: str = "CONTROLLED", before_provider_attempt=None, execution_metadata: dict[str, Any] | None = None) -> None:
        self.persistence, self.evaluator, self.evidence_class = persistence, evaluator, evidence_class
        self.before_provider_attempt, self.execution_metadata = before_provider_attempt, dict(execution_metadata or {})

    def execute_single(self, *, unit: ExperimentalUnit, request: EvaluationRequest, idempotency_key: str) -> ControlledRun:
        self._validate_unit_request(unit, request)
        run = self.persistence.create_run(unit=unit, idempotency_key=idempotency_key, requested_model=request.requested_model, judge_name=request.judge_name, provider=request.provider.value, metadata_json=self.execution_metadata, evidence_class=self.evidence_class)
        # A stable idempotency key represents one scientific observation.  Never
        # re-enter provider execution for an existing terminal/in-progress run.
        if run.status != "PENDING":
            return run
        self.persistence.mark_running(run)
        result = self._execute_with_retries(run, request)
        self._record(run, request, result)
        self._update_run_identity(run, result)
        self.persistence.complete_run(run=run, outcome=result.outcome, latency_ms=result.latency_ms, api_response_id=result.provider_response_id, error_code=result.error_code, error_details=result.error_details, retry_count=request.retry_count, final_explanation=result.explanation, final_criteria=result.criterion_scores, final_confidence=result.confidence)
        return run

    def execute_dual(self, *, unit: ExperimentalUnit, first_request: EvaluationRequest, idempotency_key: str) -> ControlledRun:
        self._validate_unit_request(unit, first_request)
        if first_request.pass_number != 1:
            raise ValueError("Dual-pass evaluation must begin with pass_number=1")
        second_request = first_request.model_copy(update={
            "answer_a": first_request.answer_b, "answer_b": first_request.answer_a,
            "presented_answer_a_id": first_request.original_answer_b_id,
            "presented_answer_b_id": first_request.original_answer_a_id, "pass_number": 2,
        })
        run = self.persistence.create_run(unit=unit, idempotency_key=idempotency_key, requested_model=first_request.requested_model, judge_name=first_request.judge_name, provider=first_request.provider.value, run_kind="CALIBRATED_DUAL_PASS", metadata_json=self.execution_metadata, evidence_class=self.evidence_class)
        existing = {p.pass_number: p for p in run.passes}
        # Resume at pass level.  A persisted successful first pass is never
        # sent again merely because a later pass did not complete.
        if run.status == "SUCCEEDED" or len(existing) == 2:
            return run
        self.persistence.mark_running(run)
        if 1 not in existing:
            first = self._execute_with_retries(run, first_request)
            self._record(run, first_request, first)
        else:
            first = self._result_from_pass(existing[1])
        if 2 not in existing:
            second = self._execute_with_retries(run, second_request)
            self._record(run, second_request, second)
        else:
            second = self._result_from_pass(existing[2])
        self._update_run_identity(run, first)
        decision = derive_dual_pass_decision(first_request, first, second_request, second)
        self.persistence.complete_dual_run(run=run, decision=decision.classification, outcome=decision.final_outcome, latency_ms=first.latency_ms + second.latency_ms, retry_count=first_request.retry_count + second_request.retry_count, final_explanation="Derived from two independently persisted presentation passes.")
        return run

    @staticmethod
    def _result_from_pass(record) -> NormalizedEvaluationResult:
        outcome = Outcome(record.outcome) if record.outcome else {"ANSWER_A": Outcome.ANSWER_A, "ANSWER_B": Outcome.ANSWER_B, "TIE": Outcome.TIE, "UNKNOWN": Outcome.UNKNOWN}.get(record.raw_verdict, Outcome.INVALID_RESPONSE)
        return NormalizedEvaluationResult(outcome, record.criteria_scores, record.confidence, record.explanation, record.raw_provider_response, record.effective_model or "NOT_RETURNED", record.model_version, record.api_response_id, record.provider_model or "NOT_RETURNED", record.latency_ms or 0, record.parse_status, route_provenance=record.route_provenance_json)

    @staticmethod
    def _validate_unit_request(unit: ExperimentalUnit, request: EvaluationRequest) -> None:
        if request.experiment_id != unit.experiment_id or request.controlled_unit_id != unit.id:
            raise ValueError("request experiment/unit identity does not match the controlled unit")
        if (request.original_answer_a_id, request.original_answer_b_id) != (unit.answer_a_id, unit.answer_b_id):
            raise ValueError("request original answer IDs do not match the controlled unit")
        if request.repetition_index != unit.repetition_index or request.prompt_template_version != unit.prompt_template_version:
            raise ValueError("request repetition or prompt template does not match the controlled unit")
        if unit.presentation_order in {"SELF_A", "SELF_B"}:
            source = {"gpt-4": "openai", "gpt-3.5-turbo": "openai", "claude-v1": "anthropic", "llama-13b": "meta-llama"}
            self_family = get_model_spec(unit.judge_model).family
            answer_family = {
                unit.answer_a_id: source.get(unit.answer_a_author_id or ""),
                unit.answer_b_id: source.get(unit.answer_b_author_id or ""),
            }
            self_id = next((answer_id for answer_id, family in answer_family.items() if family == self_family), None)
            expected_slot_id = request.presented_answer_a_id if unit.presentation_order == "SELF_A" else request.presented_answer_b_id
            if self_id is None or expected_slot_id != self_id:
                raise ValueError(f"{unit.presentation_order} requires the self-family answer in that physical presentation slot")

    def _record(self, run: ControlledRun, request: EvaluationRequest, result: NormalizedEvaluationResult) -> None:
        raw = result.raw_response if isinstance(result.raw_response, dict) else {"unparsed_response": repr(result.raw_response)}
        self.persistence.record_pass(run=run, observation=PassObservation(request.pass_number, request.presented_answer_a_id, request.presented_answer_b_id, result.outcome, confidence=result.confidence, raw_provider_response=raw, reasoning_summary=result.explanation, api_response_id=result.provider_response_id, effective_model=result.effective_model, provider_model=result.upstream_provider_model, model_version=result.model_version, latency_ms=result.latency_ms, criteria_scores=result.criterion_scores, explanation=result.explanation, route_provenance=result.route_provenance, presentation_provenance=getattr(request, "presentation_provenance", None)))
        # The relationship may have been read for resume before the insert.
        # Expire it so callers observe independently persisted passes.
        self.persistence.session.expire(run, ["passes"])

    def _execute_pass(self, run: ControlledRun, request: EvaluationRequest) -> NormalizedEvaluationResult:
        attempt = self.persistence.begin_attempt(run=run, pass_number=request.pass_number)
        if attempt.state == "SUCCEEDED":
            existing = next(p for p in run.passes if p.pass_number == request.pass_number)
            return self._result_from_pass(existing)
        reservation: dict[str, Any] = {}
        try:
            if self.before_provider_attempt is not None:
                reservation = dict(self.before_provider_attempt(run, request) or {})
            result = self.evaluator.evaluate(request)
        except PermissionError as exc:
            # A local authorization/budget guard fires before the adapter is
            # entered.  Preserve that blocked attempt without treating it as
            # ambiguous or permitting a retry/transport call.
            self.persistence.finish_attempt(attempt, state="FAILED_FINAL", failure_category="BUDGET_EXCEEDED", details={"retry_count": request.retry_count, "repetition_index": request.repetition_index, "blocked_before_transport": True, "reason": str(exc)})
            return self.evaluator._failure(Outcome.API_ERROR, perf_counter(), "BUDGET_EXCEEDED", str(exc))
        except BaseException as exc:
            # Process termination after an outbound request is potentially paid
            # and cannot be retried automatically on resume.
            self.persistence.finish_attempt(attempt, state="AMBIGUOUS", failure_category="AMBIGUOUS", details={"exception": type(exc).__name__})
            raise
        category = result.error_code or {Outcome.API_ERROR: "PROVIDER_ERROR", Outcome.TIMEOUT: "TIMEOUT", Outcome.INVALID_RESPONSE: "INVALID_RESPONSE", Outcome.REFUSAL: "REFUSAL"}.get(result.outcome)
        state = "SUCCEEDED" if result.outcome not in {Outcome.API_ERROR, Outcome.TIMEOUT, Outcome.INVALID_RESPONSE, Outcome.REFUSAL} else terminal_state(category or "CONFIGURATION", request.retry_count)
        estimated_usd_raw = reservation.get("estimated_usd")
        estimated_usd = Decimal(str(estimated_usd_raw)) if estimated_usd_raw is not None else None
        actual_usd = None
        if result.input_tokens is not None and result.output_tokens is not None:
            # The reservation uses the same frozen prices; actual provider
            # usage is retained separately whenever the response reports it.
            from pricing import price_for_model
            rate = price_for_model(request.judge_name)
            actual_usd = (Decimal(result.input_tokens) * rate.input_per_token) + (Decimal(result.output_tokens) * rate.output_per_token)
        self.persistence.finish_attempt(attempt, state=state, failure_category=category, provider_response_id=result.provider_response_id, details={"retry_count": request.retry_count, "planned_backoff_seconds": next_backoff_seconds(category or "CONFIGURATION", request.retry_count), "repetition_index": request.repetition_index, **reservation}, route_provenance=result.route_provenance, input_tokens=result.input_tokens, output_tokens=result.output_tokens, estimated_usd=estimated_usd, actual_usd=actual_usd)
        return result

    def _execute_with_retries(self, run: ControlledRun, request: EvaluationRequest) -> NormalizedEvaluationResult:
        """Retry a transport attempt, never a scientific pass/repetition."""
        current = request
        while True:
            result = self._execute_pass(run, current)
            category = result.error_code or {Outcome.API_ERROR: "PROVIDER_ERROR", Outcome.TIMEOUT: "TIMEOUT", Outcome.INVALID_RESPONSE: "INVALID_RESPONSE", Outcome.REFUSAL: "REFUSAL"}.get(result.outcome, "CONFIGURATION")
            if result.outcome not in {Outcome.API_ERROR, Outcome.TIMEOUT, Outcome.INVALID_RESPONSE, Outcome.REFUSAL} or not retry_rule(category).retryable:
                run.retry_count = current.retry_count
                return result
            if terminal_state(category, current.retry_count) != "FAILED_RETRYABLE":
                run.retry_count = current.retry_count
                return result
            # A scheduler may honor the recorded backoff.  No sleep occurs here
            # so database transactions remain short and deterministic in tests.
            current = current.model_copy(update={"retry_count": current.retry_count + 1})

    @staticmethod
    def _update_run_identity(run: ControlledRun, result: NormalizedEvaluationResult) -> None:
        run.effective_model = result.effective_model
        run.provider_model = result.upstream_provider_model
        run.model_version = result.model_version
