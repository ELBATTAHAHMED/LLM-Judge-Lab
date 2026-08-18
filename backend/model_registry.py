"""Explicit, offline-safe registry for controlled judge execution.

The registry records the exact configured judge identity.  It deliberately
does not resolve aliases or substitute a local model for a hosted model.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Provider(str, Enum):
    OPENAI = "OPENAI"
    OPENROUTER = "OPENROUTER"
    OLLAMA = "OLLAMA"


class UnsupportedModelError(ValueError):
    """Raised when controlled execution requests an unregistered model."""


@dataclass(frozen=True)
class ModelSpec:
    judge_name: str
    provider: Provider
    requested_model: str
    provider_model_id: str
    family: str
    supports_seed: bool
    supports_temperature: bool
    supports_top_p: bool
    supports_structured_json: bool
    max_output_tokens: int
    enabled: bool = True


MODEL_REGISTRY: dict[str, ModelSpec] = {
    "gpt-4o-mini": ModelSpec("gpt-4o-mini", Provider.OPENAI, "gpt-4o-mini", "gpt-4o-mini", "openai", True, True, True, True, 350),
    "anthropic/claude-3-haiku": ModelSpec("anthropic/claude-3-haiku", Provider.OPENROUTER, "anthropic/claude-3-haiku", "anthropic/claude-3-haiku", "anthropic", False, True, True, True, 350),
    "deepseek/deepseek-chat": ModelSpec("deepseek/deepseek-chat", Provider.OPENROUTER, "deepseek/deepseek-chat", "deepseek/deepseek-chat", "deepseek", False, True, True, True, 350),
    "meta-llama/llama-3.3-70b-instruct": ModelSpec("meta-llama/llama-3.3-70b-instruct", Provider.OPENROUTER, "meta-llama/llama-3.3-70b-instruct", "meta-llama/llama-3.3-70b-instruct", "meta-llama", False, True, True, True, 350),
}


def get_model_spec(judge_name: str) -> ModelSpec:
    try:
        spec = MODEL_REGISTRY[judge_name]
    except KeyError as exc:
        raise UnsupportedModelError(
            f"Unsupported controlled judge {judge_name!r}; use an exact registry key. "
            "No model alias or fallback will be applied."
        ) from exc
    if not spec.enabled:
        raise UnsupportedModelError(f"Controlled judge {judge_name!r} is disabled.")
    return spec
