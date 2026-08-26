"""Deterministic provider substitute used exclusively by offline tests."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

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


class FinalPayloadMockTransport:
    """Fake HTTP boundary that receives the actual provider-bound payload.

    It intentionally sits below ``ControlledChatAdapter``: prompt construction,
    capabilities, routing controls, headers, and parser behavior therefore run
    exactly as they will for a future authorized transport.
    """
    def __init__(self, scenarios: list[MockScenario], *, counters: dict[str, Any] | None = None) -> None:
        self.scenarios = list(scenarios); self.calls = 0; self.counters = counters if counters is not None else {}

    def __call__(self, endpoint: str, headers: Mapping[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        if not self.scenarios: raise MockProviderError("No final-payload mock scenario configured")
        self.calls += 1
        self.counters["provider_bound_requests"] = self.counters.get("provider_bound_requests", 0) + 1
        self.counters.setdefault("models", {}).setdefault(payload["model"], 0); self.counters["models"][payload["model"]] += 1
        self.counters.setdefault("prompt_versions", set()).add("controlled-judge-pairwise-v1")
        if "openrouter.ai" in endpoint:
            controls = payload.get("provider", {}); upstream = (controls.get("only") or [None])[0]
            if headers.get("X-OpenRouter-Metadata") != "enabled": raise MockProviderError("missing router metadata header")
            if controls.get("allow_fallbacks") is not False or controls.get("require_parameters") is not True or upstream is None: raise MockProviderError("invalid frozen router controls")
            self.counters.setdefault("upstreams", {}).setdefault(upstream, 0); self.counters["upstreams"][upstream] += 1
        else:
            upstream = None
        scenario = self.scenarios.pop(0)
        if scenario is MockScenario.TIMEOUT: raise TimeoutError("deterministic final-payload timeout")
        if scenario is MockScenario.PROVIDER_ERROR: raise MockProviderError("deterministic final-payload provider error")
        if scenario in {MockScenario.RATE_LIMIT, MockScenario.HTTP_5XX, MockScenario.CONNECTION, MockScenario.REFUSAL, MockScenario.AUTH, MockScenario.UNSUPPORTED_CONFIG}:
            raise ProviderCallError(scenario.value, f"deterministic final-payload {scenario.value}")
        content: Any = {"not": "a complete judgement"} if scenario is MockScenario.INVALID_JSON else {"verdict": scenario.value, "criteria_scores": {"correctness": 4, "relevance": 4, "completeness": 4, "clarity": 4, "safety": 5}, "confidence": 0.75, "explanation": "Deterministic final-payload mock judgement."}
        response: dict[str, Any] = {"id": f"final-mock-{self.calls}", "model": payload["model"], "choices": [{"message": {"content": content}}]}
        if upstream is not None: response["provider"] = {"provider": upstream, "fallbacks": []}
        return response
