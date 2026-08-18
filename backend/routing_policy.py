"""Frozen OpenRouter routing boundary for controlled experiments."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROUTING_CONFIG_PATH = Path(__file__).with_name("routing_config.json")


def routing_config() -> dict[str, Any]:
    return json.loads(ROUTING_CONFIG_PATH.read_text(encoding="utf-8"))


def routing_policy_version() -> str:
    return str(routing_config()["version"])


def routing_fingerprint() -> str:
    return hashlib.sha256(json.dumps(routing_config(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def frozen_openrouter_route(judge_name: str) -> dict[str, Any]:
    config = routing_config()
    route = config.get("models", {}).get(judge_name)
    if config.get("status") != "VERIFIED_EXTERNAL_2026_08_18" or not isinstance(route, dict) or not route.get("upstream_provider"):
        raise ValueError("OpenRouter routing is not officially verified/frozen; controlled transport is blocked")
    return route


def openrouter_request_controls(judge_name: str) -> tuple[dict[str, str], dict[str, Any]]:
    config = routing_config(); route = frozen_openrouter_route(judge_name)
    policy = config["policy"]
    return (
        {"X-OpenRouter-Metadata": "enabled"},
        {"provider": {"order": [route["upstream_provider"]], "only": [route["upstream_provider"]], "allow_fallbacks": False, "require_parameters": True}},
    )


def validate_router_response(*, judge_name: str, response: dict[str, Any]) -> None:
    """Reject missing/changed upstream provenance before evidence persistence."""
    route = frozen_openrouter_route(judge_name)
    metadata = response.get("provider") or response.get("metadata") or {}
    upstream = metadata.get("provider") or metadata.get("upstream_provider")
    if not upstream:
        raise ValueError("OpenRouter response missing required router metadata")
    if upstream != route["upstream_provider"]:
        raise ValueError("OpenRouter response was served by an unexpected upstream provider")
    if metadata.get("fallbacks") or metadata.get("fallback_attempted"):
        raise ValueError("OpenRouter fallback metadata is forbidden for controlled evidence")
