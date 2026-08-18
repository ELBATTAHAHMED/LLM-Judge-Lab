"""Locked, fixture-testable controlled provider adapters.

Adapters have no default transport and cannot contact a provider until a
future caller supplies an explicitly authorized transport and execution gate.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from controlled_evaluation import EvaluationRequest, ProviderResponse
from controlled_prompt import PROMPT_TEMPLATE_VERSION, build_messages
from model_registry import Provider, get_model_spec
from routing_policy import openrouter_request_controls, validate_router_response

Transport = Callable[[str, Mapping[str, str], dict[str, Any]], dict[str, Any]]


def _json_payload(raw: Any) -> Any:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return raw
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0].strip()
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end >= start:
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return raw


@dataclass(frozen=True)
class ProviderExecutionGate:
    mode: str = "LOCKED"
    authorization_token: str | None = None
    verified_pricing_version: str | None = None
    max_provider_calls: int = 0
    max_input_tokens: int = 0
    max_output_tokens: int = 0
    max_usd: float | None = None

    def assert_authorized(self) -> None:
        if self.mode != "REAL" or not self.authorization_token or not self.verified_pricing_version or self.max_provider_calls < 1 or self.max_input_tokens < 1 or self.max_output_tokens < 1 or self.max_usd is None:
            raise PermissionError("Real controlled execution is locked: explicit REAL profile, authorization, limits, and verified pricing are required before any provider request.")


class ControlledChatAdapter:
    def __init__(self, *, provider: Provider, transport: Transport | None = None, gate: ProviderExecutionGate = ProviderExecutionGate()) -> None:
        self.provider, self.transport, self.gate = provider, transport, gate

    def evaluate(self, request: EvaluationRequest) -> ProviderResponse:
        spec = get_model_spec(request.judge_name)
        if request.prompt_template_version != PROMPT_TEMPLATE_VERSION or request.provider is not self.provider or spec.provider is not self.provider:
            raise ValueError("controlled adapter request does not match the frozen prompt/model route")
        if not spec.supports_structured_json:
            raise ValueError("frozen controlled protocol requires structured JSON; provider configuration is unsupported")
        self.gate.assert_authorized()
        if self.transport is None:
            raise RuntimeError("No authorized controlled transport configured")
        payload: dict[str, Any] = {"model": spec.provider_model_id, "messages": build_messages(question=request.question, answer_a=request.answer_a, answer_b=request.answer_b), "temperature": request.temperature, "top_p": request.top_p, "max_tokens": spec.max_output_tokens}
        headers: dict[str, str] = {}
        if self.provider is Provider.OPENROUTER:
            # This rejects every unverified route before any transport call.
            metadata_headers, routing_controls = openrouter_request_controls(request.judge_name)
            headers.update(metadata_headers); payload.update(routing_controls)
        if request.seed is not None:
            payload["seed"] = request.seed
        endpoint = "https://api.openai.com/v1/chat/completions" if self.provider is Provider.OPENAI else "https://openrouter.ai/api/v1/chat/completions"
        response = self.transport(endpoint, headers, payload)
        if self.provider is Provider.OPENROUTER:
            validate_router_response(judge_name=request.judge_name, response=response)
        choices = response.get("choices") or []
        message = choices[0].get("message", {}) if choices else {}
        content = message.get("content") if isinstance(message, dict) else None
        return ProviderResponse(raw_response=_json_payload(content), effective_model=response.get("model"), model_version=response.get("system_fingerprint"), provider_response_id=response.get("id"), upstream_provider_model=response.get("model"))


def adapter_for_judge(judge_name: str, *, transport: Transport | None = None, gate: ProviderExecutionGate = ProviderExecutionGate()) -> ControlledChatAdapter:
    return ControlledChatAdapter(provider=get_model_spec(judge_name).provider, transport=transport, gate=gate)
