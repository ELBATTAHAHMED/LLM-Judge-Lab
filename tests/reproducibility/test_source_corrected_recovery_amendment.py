"""Provider-free checks for the additive source-corrected recovery design."""
from __future__ import annotations

from build_source_corrected_recovery_amendment import build
from source_corrected_execution import stable_sha


def test_recovery_amendment_targets_only_terminal_missing_logical_slots():
    manifest, _amendment = build()
    assert manifest["counts"]["total_recovery_slots"] == 119
    assert manifest["counts"]["failed_replacements"] == 118
    assert manifest["counts"]["ambiguous_replacements"] == 1
    assert manifest["counts"]["completed_slot_overlap"] == 0
    assert len({row["recovery_idempotency_key"] for row in manifest["recovery_slots"]}) == 119
    assert {row["historical_terminal_state"] for row in manifest["recovery_slots"]} == {"FAILED", "AMBIGUOUS"}


def test_recovery_amendment_preserves_frozen_configuration_and_deterministic_hashes():
    manifest, amendment = build()
    for row in manifest["recovery_slots"]:
        assert row["rendered_payload_sha256"]
        assert row["prompt_sha256"]
        assert row["judge_id"] and row["provider"] and row["route"]
        assert row["replacement_counting_rule"].startswith("ONE_VALID_RECOVERY_RESULT")
    manifest_for_hash = dict(manifest)
    manifest_for_hash.pop("recovery_manifest_sha256")
    amendment_for_hash = dict(amendment)
    amendment_for_hash.pop("amendment_sha256")
    assert stable_sha(manifest_for_hash) == manifest["recovery_manifest_sha256"]
    assert stable_sha(amendment_for_hash) == amendment["amendment_sha256"]
    assert amendment["execution_plan"]["provider_execution_authorized"] is False
    assert amendment["provider_calls"] == 0
