"""Fail-closed, controlled-only real/pilot execution boundary.

This module deliberately accepts a transport dependency.  Production can supply
the HTTP transport only after an operator has loaded credentials; tests supply a
fake transport.  No legacy evaluator is reachable from this boundary.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from sqlalchemy.orm import Session

from controlled_evaluation import ControlledEvaluationEngine, ControlledExecutionService, EvaluationRequest
from controlled_models import Experiment, ExperimentalUnit, ExperimentManifest
from controlled_persistence import ControlledPersistence
from controlled_providers import ProviderExecutionGate, Transport, adapter_for_judge, environment_http_transport
from controlled_prompt import PROMPT_TEMPLATE_VERSION, prompt_hash
from model_registry import get_model_spec
from execution_policy import FAILURE_POLICY_VERSION, RETRY_POLICY_VERSION
from pricing import CONFIG as PRICING_CONFIG, price_for_model
from routing_policy import frozen_openrouter_route, routing_fingerprint, routing_policy_version


PROFILE_VERSION = "controlled-real-profile-v1"


@dataclass(frozen=True)
class ExecutionCaps:
    max_scientific_passes: int
    max_provider_attempts: int
    max_input_tokens: int
    max_output_tokens: int
    max_usd: Decimal


@dataclass(frozen=True)
class RealExecutionProfile:
    """Immutable profile required before the first provider-bound request."""
    execution_mode: str
    authorization_token: str | None
    dataset_version_id: str
    manifest_ids: tuple[str, ...]
    manifest_hashes: tuple[str, ...]
    source_commit: str
    source_tag: str
    pricing_version: str
    routing_version: str
    routing_fingerprint: str
    prompt_version: str
    prompt_sha256: str
    retry_policy_version: str
    failure_policy_version: str
    analysis_version: str
    model_ids: tuple[str, ...]
    configured_upstreams: tuple[str, ...]
    caps: ExecutionCaps
    profile_version: str = PROFILE_VERSION
    evidence_class: str = "CONTROLLED"

    def provenance_snapshot(self) -> dict[str, Any]:
        """Non-secret immutable run provenance; authorization is never stored."""
        return {
            "profile_version": self.profile_version,
            "execution_mode": self.execution_mode,
            "evidence_class": self.evidence_class,
            "dataset_version_id": self.dataset_version_id,
            "manifest_ids": list(self.manifest_ids),
            "manifest_hashes": list(self.manifest_hashes),
            "source_commit": self.source_commit,
            "source_tag": self.source_tag,
            "pricing_version": self.pricing_version,
            "routing_version": self.routing_version,
            "routing_fingerprint": self.routing_fingerprint,
            "prompt_version": self.prompt_version,
            "prompt_sha256": self.prompt_sha256,
            "retry_policy_version": self.retry_policy_version,
            "failure_policy_version": self.failure_policy_version,
            "analysis_version": self.analysis_version,
            "model_ids": list(self.model_ids),
            "configured_upstreams": list(self.configured_upstreams),
            "caps": {"max_scientific_passes": self.caps.max_scientific_passes, "max_provider_attempts": self.caps.max_provider_attempts, "max_input_tokens": self.caps.max_input_tokens, "max_output_tokens": self.caps.max_output_tokens, "max_usd": str(self.caps.max_usd)},
        }

    def assert_authorized(self) -> None:
        if self.execution_mode not in {"REAL", "PILOT"}:
            raise PermissionError("controlled execution profile is not REAL/PILOT")
        if not self.authorization_token:
            raise PermissionError("explicit controlled execution authorization is required")
        if self.evidence_class not in {"CONTROLLED", "PILOT"}:
            raise PermissionError("execution profile has an invalid evidence class")
        if self.execution_mode == "PILOT" and self.evidence_class != "PILOT":
            raise PermissionError("pilot execution must remain outside final controlled evidence")
        if self.execution_mode == "REAL" and self.evidence_class != "CONTROLLED":
            raise PermissionError("real final execution must be CONTROLLED evidence")
        if not self.manifest_ids or len(self.manifest_ids) != len(self.manifest_hashes):
            raise PermissionError("exact frozen manifest IDs/hashes are required")
        if not self.model_ids or not self.configured_upstreams:
            raise PermissionError("exact configured model IDs and upstreams are required")
        if tuple(sorted(self.model_ids)) != tuple(sorted(get_model_spec(name).requested_model for name in self.model_ids)):
            raise PermissionError("execution profile contains an unknown or non-canonical model ID")
        expected_upstreams = {
            frozen_openrouter_route(model)["upstream_provider"]
            for model in self.model_ids
            if get_model_spec(model).provider.value == "OPENROUTER"
        }
        if set(self.configured_upstreams) != expected_upstreams:
            raise PermissionError("execution profile upstreams do not match frozen routing")
        if self.pricing_version != PRICING_CONFIG.get("version"):
            raise PermissionError("execution profile pricing version does not match the frozen pricing configuration")
        if self.retry_policy_version != RETRY_POLICY_VERSION or self.failure_policy_version != FAILURE_POLICY_VERSION:
            raise PermissionError("execution profile retry/failure policy versions do not match code")
        if self.prompt_version != PROMPT_TEMPLATE_VERSION or self.prompt_sha256 != prompt_hash():
            raise PermissionError("frozen prompt profile does not match current code")
        if self.routing_version != routing_policy_version() or self.routing_fingerprint != routing_fingerprint():
            raise PermissionError("frozen routing profile does not match current code")
        root = Path(__file__).resolve().parent.parent
        try:
            commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            tag = subprocess.check_output(["git", "describe", "--tags", "--exact-match", "HEAD"], cwd=root, text=True).strip()
        except Exception as exc:
            raise PermissionError("source commit/tag cannot be verified for real execution") from exc
        if self.source_commit != commit or self.source_tag != tag:
            raise PermissionError("real execution profile source commit/tag does not match repository")
        if min(self.caps.max_scientific_passes, self.caps.max_provider_attempts, self.caps.max_input_tokens, self.caps.max_output_tokens) < 1 or self.caps.max_usd < 0:
            raise PermissionError("non-zero hard scientific/attempt/token/USD caps are required")

    def verify_manifest(self, session: Session, unit: ExperimentalUnit) -> None:
        self.assert_authorized()
        manifest = session.get(ExperimentManifest, unit.manifest_id)
        if manifest is None or str(manifest.id) not in self.manifest_ids or manifest.manifest_sha256 not in self.manifest_hashes:
            raise PermissionError("unit is outside the frozen execution profile")
        material = manifest.manifest_json or {}
        if material.get("prompt_hash") != self.prompt_sha256 or material.get("routing_policy_version") != self.routing_version or material.get("routing_fingerprint") != self.routing_fingerprint:
            raise PermissionError("manifest prompt/routing identity does not match the real execution profile")
        experiment = session.get(Experiment, unit.experiment_id)
        if experiment is None or str(experiment.dataset_version_id) != self.dataset_version_id:
            raise PermissionError("unit dataset version does not match the real execution profile")
        if str(unit.experiment_id) == "":  # defensive impossible-state guard
            raise PermissionError("unit has no experiment identity")


@dataclass
class BudgetLedger:
    """Pre-request reservation ledger; caps are checked before transport."""
    profile: RealExecutionProfile
    scientific_passes: set[tuple[str, int]] = field(default_factory=set)
    provider_attempts: int = 0
    reserved_input_tokens: int = 0
    reserved_output_tokens: int = 0
    reserved_usd: Decimal = Decimal("0")

    @staticmethod
    def _estimate_input(request: EvaluationRequest) -> int:
        # Conservative provider-neutral estimate; cap is checked before HTTP.
        return (len(request.question) + len(request.answer_a) + len(request.answer_b) + 600 + 3) // 4

    def reserve(self, *, run_id: str, request: EvaluationRequest) -> dict[str, Any]:
        spec = get_model_spec(request.judge_name)
        estimated_input = self._estimate_input(request)
        estimated_output = spec.max_output_tokens
        rate = price_for_model(request.judge_name)
        estimated_usd = (Decimal(estimated_input) * rate.input_per_token) + (Decimal(estimated_output) * rate.output_per_token)
        scientific = set(self.scientific_passes); scientific.add((run_id, request.pass_number))
        if (len(scientific) > self.profile.caps.max_scientific_passes or self.provider_attempts + 1 > self.profile.caps.max_provider_attempts or
                self.reserved_input_tokens + estimated_input > self.profile.caps.max_input_tokens or
                self.reserved_output_tokens + estimated_output > self.profile.caps.max_output_tokens or
                self.reserved_usd + estimated_usd > self.profile.caps.max_usd):
            raise PermissionError("controlled budget guard stopped execution before provider transport")
        self.scientific_passes = scientific
        self.provider_attempts += 1
        self.reserved_input_tokens += estimated_input
        self.reserved_output_tokens += estimated_output
        self.reserved_usd += estimated_usd
        return {"estimated_input_tokens": estimated_input, "estimated_output_tokens": estimated_output,
                "estimated_usd": estimated_usd}

    def snapshot(self) -> dict[str, Any]:
        return {"scientific_passes": len(self.scientific_passes), "provider_attempts": self.provider_attempts,
                "reserved_input_tokens": self.reserved_input_tokens, "reserved_output_tokens": self.reserved_output_tokens,
                "reserved_usd": str(self.reserved_usd)}


class ControlledRealRunner:
    """The sole authorized final/pilot execution entry point."""
    def __init__(self, *, profile: RealExecutionProfile, transport: Transport | None = None) -> None:
        profile.assert_authorized()
        self.profile, self.transport, self.ledger = profile, transport or environment_http_transport, BudgetLedger(profile)

    def execute(self, *, session: Session, unit: ExperimentalUnit, request: EvaluationRequest, idempotency_key: str, dual_pass: bool) -> Any:
        self.profile.verify_manifest(session, unit)
        gate = ProviderExecutionGate(mode="REAL", authorization_token=self.profile.authorization_token,
            verified_pricing_version=self.profile.pricing_version, max_provider_calls=self.profile.caps.max_provider_attempts,
            max_input_tokens=self.profile.caps.max_input_tokens, max_output_tokens=self.profile.caps.max_output_tokens,
            max_usd=float(self.profile.caps.max_usd))
        repo = ControlledPersistence(session)
        service = ControlledExecutionService(repo, ControlledEvaluationEngine(adapter_for_judge(request.judge_name, transport=self.transport, gate=gate)),
            evidence_class=self.profile.evidence_class, before_provider_attempt=lambda run, req: self.ledger.reserve(run_id=str(run.id), request=req),
            execution_metadata={"execution_profile": self.profile.provenance_snapshot(), "budget": self.ledger.snapshot(), "routing_policy_version": self.profile.routing_version, "routing_fingerprint": self.profile.routing_fingerprint})
        return service.execute_dual(unit=unit, first_request=request, idempotency_key=idempotency_key) if dual_pass else service.execute_single(unit=unit, request=request, idempotency_key=idempotency_key)
