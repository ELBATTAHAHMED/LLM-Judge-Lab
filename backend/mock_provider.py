"""Deterministic provider substitute used exclusively by offline tests."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from controlled_persistence import Outcome
from controlled_evaluation import ProviderCallError


class MockScenario(str, Enum):
    ANSWER_A = "ANSWER_A"
    ANSWER_B = "ANSWER_B"
    TIE = "TIE"
    UNKNOWN = "UNKNOWN"
    INVALID_JSON = "INVALID_JSON"
    TIMEOUT = "TIMEOUT"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    RATE_LIMIT = "RATE_LIMIT"
    HTTP_5XX = "HTTP_5XX"
    CONNECTION = "CONNECTION"
    REFUSAL = "REFUSAL"
    AUTH = "AUTH"
    UNSUPPORTED_CONFIG = "UNSUPPORTED_CONFIG"


class MockProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class MockProviderResponse:
    raw_response: Any
    effective_model: str | None = None
    model_version: str | None = None
    provider_response_id: str | None = None
    upstream_provider_model: str | None = None


class DeterministicMockProvider:
    """A queue-driven fake; it never imports or contacts a provider SDK."""

    def __init__(self, scenarios: list[MockScenario], *, effective_model: str | None = "mock-effective-v1") -> None:
        self.scenarios = list(scenarios)
        self.effective_model = effective_model
        self.calls = 0

    def evaluate(self, request: Any) -> MockProviderResponse:
        if not self.scenarios:
            raise MockProviderError("No mock scenario configured")
        scenario = self.scenarios.pop(0)
        self.calls += 1
        if scenario is MockScenario.TIMEOUT:
            raise TimeoutError("deterministic mock timeout")
        if scenario is MockScenario.PROVIDER_ERROR:
            raise MockProviderError("deterministic mock provider error")
        if scenario in {MockScenario.RATE_LIMIT, MockScenario.HTTP_5XX, MockScenario.CONNECTION, MockScenario.REFUSAL, MockScenario.AUTH, MockScenario.UNSUPPORTED_CONFIG}:
            raise ProviderCallError(scenario.value, f"deterministic mock {scenario.value}")
        if scenario is MockScenario.INVALID_JSON:
            return MockProviderResponse(raw_response={"not": "a complete judgement"}, effective_model=self.effective_model)
        return MockProviderResponse(
            raw_response={
                "verdict": scenario.value,
                "criteria_scores": {"correctness": 4, "relevance": 4, "completeness": 4, "clarity": 4, "safety": 5},
                "confidence": 0.75,
                "explanation": "Deterministic offline mock judgement.",
            },
            effective_model=self.effective_model,
            model_version="mock-version-1",
            provider_response_id=f"mock-{self.calls}",
            upstream_provider_model="NOT_RETURNED",
        )
