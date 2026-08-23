"""Provider-free full-manifest rehearsal and safety checks."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest

from multijudge_execution import (
    CrashPoint, DeterministicMockTransport, MockResponse, MockTransportFailure,
    MultiJudgeDryRunExecutor, RealProviderTransport, RealTransportForbidden, SimulatedCrash,
)


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "evidence" / "multijudge_consensus" / "execution_manifest_v1.json"


def executor(*, scripted=None, enforce_budget=False, cap=None, ledger_path=None):
    return MultiJudgeDryRunExecutor(MANIFEST, DeterministicMockTransport(scripted), enforce_budget=enforce_budget, budget_cap_usd=cap, ledger_path=ledger_path)


def test_full_6444_manifest_mock_run_resume_and_idempotency():
    run = executor()
    assert run.run(limit=3000) == {"COMPLETED": 3000, "PENDING": 3444}
    first_calls = run.transport.calls
    assert first_calls == 3000
    assert run.run(limit=444) == {"COMPLETED": 3444, "PENDING": 3000}
    assert run.run() == {"COMPLETED": 6444}
    assert run.transport.calls == 6444
    assert run.run() == {"COMPLETED": 6444}  # completed slots are never replayed
    summary = run.summary()
    assert summary == {
        "planned_pairs": 1611, "planned_passes": 6444, "completed_scientific_outcomes": 6444,
        "duplicate_scientific_outcomes": 0, "missing_planned_outcomes": 0, "attempts": 6444,
        "mock_estimated_usd": pytest.approx(0.6444), "real_spend_usd": 0.0, "real_provider_calls": 0,
    }
    costs = run.cost_ledger()
    assert costs["cost_kind"] == "MOCK_ESTIMATED"
    assert costs["total_mock_estimated_usd"] == pytest.approx(0.6444)
    assert costs["total_real_actual_usd"] == 0.0
    assert costs["openai_mock_estimated_usd"] == pytest.approx(0.1611)
    assert costs["openrouter_mock_estimated_usd"] == pytest.approx(0.4833)
    assert set(costs["per_model"]) == {"gpt-4o-mini", "anthropic/claude-3-haiku", "deepseek/deepseek-chat", "meta-llama/llama-3.3-70b-instruct"}


def test_isolated_sqlite_ledger_resumes_across_a_fresh_executor_instance(tmp_path):
    ledger = tmp_path / "multijudge-rehearsal.sqlite3"
    first = executor(ledger_path=ledger)
    assert first.run(limit=12) == {"COMPLETED": 12, "PENDING": 6432}
    pass_id = next(iter(first.by_pass))
    slot = first.ledger.slot(pass_id)
    attempt = first.ledger.connection.execute("SELECT * FROM attempts WHERE planned_pass_id=?", (pass_id,)).fetchone()
    assert slot["status"] == "COMPLETED" and slot["mapped_vote"] in {"ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_2", "TIE"}
    assert slot["created_at"] and slot["completed_at"]
    assert attempt["state"] == "SUCCEEDED" and attempt["input_tokens"] > 0 and attempt["output_tokens"] == 24
    assert attempt["estimated_usd"] == pytest.approx(0.0001) and attempt["actual_usd"] == 0 and attempt["cost_kind"] == "MOCK_ESTIMATED"
    assert attempt["created_at"] and attempt["completed_at"]
    assert first.ledger.connection.execute("SELECT value FROM ledger_metadata WHERE key='manifest_sha256'").fetchone()[0] == hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    resumed = executor(ledger_path=ledger)
    assert resumed.run(limit=1) == {"COMPLETED": 13, "PENDING": 6431}
    assert resumed.transport.calls == 1  # the prior 12 persisted and were not replayed


def test_payloads_and_original_answer_round_trip_are_valid_for_every_manifest_pass():
    run = executor()
    for pass_id, item in run.by_pass.items():
        payload = run.payload(pass_id)
        assert "human_reference" not in json.dumps(payload).lower()
        assert run.map_vote(item, "A") in {"ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_2"}
        assert run.map_vote(item, "B") in {"ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_2"}
        assert run.map_vote(item, "TIE") == "TIE"
        assert run.map_vote(item, "UNKNOWN") is None


def test_fault_injection_retry_terminal_failure_and_budget_enforcement():
    first = json.loads(MANIFEST.read_text(encoding="utf-8"))["planned_passes"][0]["planned_pass_id"]
    retry = executor(scripted={first: [MockTransportFailure("TIMEOUT"), MockResponse("A", 10, 2, 0.0001)]})
    assert retry.execute_one(first) == "COMPLETED" and retry.ledger.slot(first)["attempts"] == 2
    provider_retry = executor(scripted={first: [MockTransportFailure("CONNECTION"), MockResponse("B", 10, 2, 0.0001)]})
    assert provider_retry.execute_one(first) == "COMPLETED" and provider_retry.ledger.slot(first)["mapped_vote"] in {"ORIGINAL_ANSWER_1", "ORIGINAL_ANSWER_2"}
    tied = executor(scripted={first: [MockResponse("TIE", 10, 2, 0.0001)]})
    assert tied.execute_one(first) == "COMPLETED" and tied.ledger.slot(first)["mapped_vote"] == "TIE"
    unknown = executor(scripted={first: [MockResponse("UNKNOWN", 10, 2, 0.0001)]})
    assert unknown.execute_one(first) == "COMPLETED" and unknown.ledger.slot(first)["mapped_vote"] is None
    invalid = executor(scripted={first: [MockResponse("INVALID_JSON", 10, 2, 0.0001)]})
    assert invalid.execute_one(first) == "COMPLETED" and invalid.ledger.slot(first)["final_outcome"] == "INVALID_RESPONSE"
    permanent = executor(scripted={first: [MockTransportFailure("PROVIDER_ERROR")]})
    assert permanent.execute_one(first) == "FAILED_FINAL" and permanent.ledger.slot(first)["attempts"] == 1
    error_attempt = permanent.ledger.connection.execute("SELECT state, category, completed_at FROM attempts WHERE planned_pass_id=?", (first,)).fetchone()
    assert error_attempt["state"] == "FAILED" and error_attempt["category"] == "PROVIDER_ERROR"
    assert error_attempt["completed_at"]
    exhausted = executor(scripted={first: [MockTransportFailure("CONNECTION")] * 3})
    assert exhausted.execute_one(first) == "FAILED_FINAL" and exhausted.ledger.slot(first)["attempts"] == 3
    capped = executor(enforce_budget=True, cap=0.00005)
    assert capped.execute_one(first) == "FAILED_FINAL" and capped.ledger.slot(first)["status"] == "FAILED_FINAL" and capped.transport.calls == 0
    approaching_cap = executor(enforce_budget=True, cap=0.0003)
    second = list(approaching_cap.by_pass)[1]
    assert approaching_cap.execute_one(first) == "COMPLETED"  # safely below the cap
    assert approaching_cap.execute_one(second) == "FAILED_FINAL"  # the next forecast would exceed it
    assert approaching_cap.transport.calls == 1 and approaching_cap.ledger.total_mock_estimate() == pytest.approx(0.0001)


def test_route_model_fallback_and_pricing_drift_fail_closed_before_transport():
    first = json.loads(MANIFEST.read_text(encoding="utf-8"))["planned_passes"][0]["planned_pass_id"]
    run = executor(); judge = run.by_pass[first]["judge_id"]
    run.judges[judge]["requested_model"] = "wrong-model"
    with pytest.raises(ValueError, match="provider/model"):
        run.payload(first)
    routed = executor(); routed.judges["anthropic/claude-3-haiku"]["route"] = "wrong-route"
    claude_pass = next(key for key, row in routed.by_pass.items() if row["judge_id"] == "anthropic/claude-3-haiku")
    with pytest.raises(ValueError, match="OpenRouter route"):
        routed.payload(claude_pass)
    fallback = executor(); fallback.judges[judge]["fallbacks_allowed"] = True
    with pytest.raises(ValueError, match="provider/model/fallback"):
        fallback.payload(first)
    pricing = executor(); pricing.pricing_by_judge.pop(judge)
    with pytest.raises(ValueError, match="pricing"):
        pricing.payload(first)


@pytest.mark.parametrize("point, status, calls", [
    (CrashPoint.BEFORE_TRANSPORT, "PENDING", 0),
    (CrashPoint.AFTER_TRANSPORT_BEFORE_PERSIST, "AMBIGUOUS", 1),
    (CrashPoint.DURING_PERSISTENCE, "AMBIGUOUS", 1),
    (CrashPoint.AFTER_PERSISTENCE_BEFORE_ACK, "COMPLETED", 1),
])
def test_crash_recovery_never_replays_a_possibly_sent_scientific_pass(point, status, calls):
    run = executor(); pass_id = next(iter(run.by_pass))
    with pytest.raises(SimulatedCrash):
        run.execute_one(pass_id, crash_at=point)
    assert run.ledger.slot(pass_id)["status"] == status
    before = run.transport.calls
    run.execute_one(pass_id)
    if status == "PENDING":
        assert run.transport.calls == before + 1
    else:
        assert run.transport.calls == before
    assert before == calls


def test_real_transport_is_impossible_and_reference_outcomes_are_not_loaded(monkeypatch):
    with pytest.raises(RealTransportForbidden):
        RealProviderTransport()
    import multijudge_execution
    original = multijudge_execution._copy_rows
    def reject_human_preferences(table):
        if table == "human_preferences":
            raise AssertionError("execution must not load human-reference outcomes")
        return original(table)
    monkeypatch.setattr(multijudge_execution, "_copy_rows", reject_human_preferences)
    run = executor()
    assert run.real_provider_calls == 0
    assert run.payload(next(iter(run.by_pass)))["messages"]
