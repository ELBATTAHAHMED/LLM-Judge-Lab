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


CANONICAL_PROVIDER_MAP = {
    # Amazon Bedrock aliases
    "amazon bedrock": "amazon-bedrock",
    "amazon-bedrock": "amazon-bedrock",
    "amazonbedrock": "amazon-bedrock",
    "bedrock": "amazon-bedrock",
    "amazon": "amazon-bedrock",

    # StreamLake aliases
    "streamlake": "streamlake",
    "stream lake": "streamlake",
    "stream-lake": "streamlake",
    "stream_lake": "streamlake",

    # DeepInfra aliases
    "deepinfra/turbo": "deepinfra/turbo",
    "deepinfra": "deepinfra/turbo",
    "deep infra": "deepinfra/turbo",
    "deep-infra": "deepinfra/turbo",
    "deep_infra": "deepinfra/turbo",
    "deepinfra/turbo-instruct": "deepinfra/turbo",
    "deepinfra/llama-3.3-70b-instruct": "deepinfra/turbo",
}


def normalize_provider_slug(raw_name: str | None) -> str | None:
    if not raw_name or not isinstance(raw_name, str):
        return None
    cleaned = raw_name.strip().lower()
    return CANONICAL_PROVIDER_MAP.get(cleaned, cleaned)


def extract_openrouter_routing_metadata(response: dict[str, Any]) -> tuple[str | None, str | None, bool, dict[str, Any]]:
    """Extract raw provider, canonical slug, fallback flag, and sanitized metadata from OpenRouter response."""
    raw_provider: str | None = None
    fallback_observed = False
    router_metadata: dict[str, Any] = {}

    # Priority 1: openrouter_metadata
    orm = response.get("openrouter_metadata")
    if isinstance(orm, dict):
        router_metadata["openrouter_metadata"] = orm
        if orm.get("fallback_attempted") is True or bool(orm.get("fallbacks")):
            fallback_observed = True
        attempts = orm.get("attempts")
        if isinstance(attempts, list) and len(attempts) > 1:
            fallback_observed = True

        endpoints = orm.get("endpoints")
        if isinstance(endpoints, list) and len(endpoints) > 0:
            ep = endpoints[0]
            if isinstance(ep, dict):
                raw_provider = ep.get("provider_slug") or ep.get("provider_name") or ep.get("provider")
        if not raw_provider and isinstance(attempts, list) and len(attempts) > 0:
            att = attempts[0]
            if isinstance(att, dict):
                raw_provider = att.get("provider") or att.get("provider_name")
        if not raw_provider:
            raw_provider = orm.get("selected_provider") or orm.get("provider")

    # Priority 2: provider dictionary
    prov = response.get("provider")
    if isinstance(prov, dict):
        router_metadata["provider_dict"] = prov
        if prov.get("fallbacks") or prov.get("fallback_attempted"):
            fallback_observed = True
        if not raw_provider:
            raw_provider = prov.get("provider") or prov.get("upstream_provider") or prov.get("provider_name")

    # Priority 3: top-level provider string
    if not raw_provider and isinstance(prov, str) and prov.strip():
        router_metadata["provider_string"] = prov
        raw_provider = prov.strip()

    # Priority 4: metadata dictionary
    meta = response.get("metadata")
    if isinstance(meta, dict):
        router_metadata["metadata"] = meta
        if meta.get("fallbacks") or meta.get("fallback_attempted"):
            fallback_observed = True
        if not raw_provider:
            raw_provider = meta.get("provider") or meta.get("upstream_provider")

    canonical = normalize_provider_slug(raw_provider)
    return raw_provider, canonical, fallback_observed, router_metadata


def validate_router_response(*, judge_name: str, response: dict[str, Any]) -> dict[str, Any]:
    """Reject missing/changed upstream provenance and return durable subset."""
    route = frozen_openrouter_route(judge_name)
    expected_upstream = route["upstream_provider"]
    raw_provider, canonical_provider, fallback_observed, router_metadata = extract_openrouter_routing_metadata(response)

    if not raw_provider:
        raise ValueError("OpenRouter response missing required router metadata")
    if canonical_provider != expected_upstream and raw_provider != expected_upstream:
        raise ValueError(
            f"OpenRouter response was served by an unexpected upstream provider: "
            f"observed {raw_provider!r} (canonical {canonical_provider!r}) != expected {expected_upstream!r}"
        )
    if fallback_observed:
        raise ValueError("OpenRouter fallback metadata is forbidden for controlled evidence")

    return {
        "configured_upstream_provider": expected_upstream,
        "observed_upstream_provider": canonical_provider,
        "raw_observed_upstream_provider": raw_provider,
        "routing_policy_version": routing_policy_version(),
        "routing_fingerprint": routing_fingerprint(),
        "fallback_observed": False,
        "router_metadata": router_metadata,
    }

