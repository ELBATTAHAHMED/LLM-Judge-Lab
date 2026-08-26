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

    # StreamLake aliases
    "streamlake": "streamlake",
    "stream lake": "streamlake",
    "stream-lake": "streamlake",
    "stream_lake": "streamlake",

    # DeepInfra provider family (does NOT imply /turbo)
    "deepinfra": "deepinfra",
    "deep infra": "deepinfra",
    "deep-infra": "deepinfra",
    "deep_infra": "deepinfra",

    # DeepInfra / Turbo exact endpoint variant
    "deepinfra/turbo": "deepinfra/turbo",
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

    # Priority 1: openrouter_metadata (authoritative endpoint/attempt metadata)
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
                raw_provider = ep.get("provider_slug") or ep.get("endpoint") or ep.get("provider_name") or ep.get("provider")
        elif isinstance(endpoints, dict):
            avail = endpoints.get("available")
            if isinstance(avail, list) and len(avail) > 0 and isinstance(avail[0], dict):
                raw_provider = avail[0].get("provider_slug") or avail[0].get("endpoint") or avail[0].get("provider_name") or avail[0].get("provider")
        if not raw_provider and isinstance(attempts, list) and len(attempts) > 0:
            att = attempts[0]
            if isinstance(att, dict):
                raw_provider = att.get("provider_slug") or att.get("endpoint") or att.get("provider") or att.get("provider_name")
        if not raw_provider:
            raw_provider = orm.get("selected_provider") or orm.get("provider_slug") or orm.get("provider")

    # Priority 2: provider dictionary
    prov = response.get("provider")
    if isinstance(prov, dict):
        router_metadata["provider_dict"] = prov
        if prov.get("fallbacks") or prov.get("fallback_attempted"):
            fallback_observed = True
        if not raw_provider:
            raw_provider = prov.get("provider_slug") or prov.get("endpoint") or prov.get("provider") or prov.get("upstream_provider") or prov.get("provider_name")

    # Priority 3: top-level provider string (family evidence or exact slug if given)
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
            raw_provider = meta.get("provider_slug") or meta.get("endpoint") or meta.get("provider") or meta.get("upstream_provider")

    canonical = normalize_provider_slug(raw_provider)
    return raw_provider, canonical, fallback_observed, router_metadata


def validate_router_response(
    *,
    judge_name: str,
    response: dict[str, Any],
    request_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Reject missing/changed upstream provenance and return durable subset."""
    route = frozen_openrouter_route(judge_name)
    expected_upstream = route["upstream_provider"]
    raw_provider, canonical_provider, fallback_observed, router_metadata = extract_openrouter_routing_metadata(response)

    if not raw_provider:
        raise ValueError("OpenRouter response missing required router metadata")
    if fallback_observed:
        raise ValueError("OpenRouter fallback metadata is forbidden for controlled evidence")

    expected_family = expected_upstream.split("/")[0]
    has_endpoint_subtype = "/" in expected_upstream
    observed_family = canonical_provider.split("/")[0] if canonical_provider else None
    observed_endpoint_slug = canonical_provider if (canonical_provider and "/" in canonical_provider) else None

    # Case 1: Direct response confirmation of exact endpoint or exact provider
    if canonical_provider == expected_upstream or raw_provider == expected_upstream:
        verification_basis = "RESPONSE_CONFIRMED_EXACT_ENDPOINT" if has_endpoint_subtype else "RESPONSE_CONFIRMED_EXACT_PROVIDER"
        return {
            "configured_upstream_provider": expected_upstream,
            "observed_upstream_provider": expected_upstream,
            "observed_provider_family": observed_family,
            "observed_endpoint_slug": observed_endpoint_slug,
            "raw_observed_upstream_provider": raw_provider,
            "route_verification_basis": verification_basis,
            "routing_policy_version": routing_policy_version(),
            "routing_fingerprint": routing_fingerprint(),
            "fallback_observed": False,
            "router_metadata": router_metadata,
        }

    # Case 2: Configured route has endpoint subtype (e.g. deepinfra/turbo), response confirms family (e.g. deepinfra),
    # and outbound request strictly enforced exact endpoint with no fallbacks.
    if has_endpoint_subtype and observed_family == expected_family:
        if request_payload is not None:
            req_prov = request_payload.get("provider", {}) if isinstance(request_payload.get("provider"), dict) else {}
            req_only = req_prov.get("only")
            req_allow_fallbacks = req_prov.get("allow_fallbacks")
            if req_only != [expected_upstream]:
                raise ValueError(
                    f"Outbound request constraint 'only'={req_only!r} did not enforce required exact endpoint {expected_upstream!r}"
                )
            if req_allow_fallbacks is not False:
                raise ValueError("Outbound request allowed fallbacks, which violates controlled protocol")
        else:
            _, frozen_controls = openrouter_request_controls(judge_name)
            req_prov = frozen_controls.get("provider", {})
            if req_prov.get("only") != [expected_upstream] or req_prov.get("allow_fallbacks") is not False:
                raise ValueError(f"Routing controls did not enforce required exact endpoint {expected_upstream!r}")

        verification_basis = "REQUEST_ENFORCED_EXACT_ENDPOINT_RESPONSE_CONFIRMED_FAMILY"
        return {
            "configured_upstream_provider": expected_upstream,
            "observed_upstream_provider": expected_upstream,
            "observed_provider_family": observed_family,
            "observed_endpoint_slug": None,  # Truthfully NULL because response did not echo subtype
            "raw_observed_upstream_provider": raw_provider,
            "route_verification_basis": verification_basis,
            "routing_policy_version": routing_policy_version(),
            "routing_fingerprint": routing_fingerprint(),
            "fallback_observed": False,
            "router_metadata": router_metadata,
        }

    raise ValueError(
        f"OpenRouter response was served by an unexpected upstream provider: "
        f"observed {raw_provider!r} (canonical {canonical_provider!r}) != expected {expected_upstream!r}"
    )

