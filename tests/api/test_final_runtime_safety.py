"""Provider-free regression tests for final application safety boundaries."""
from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace

import main
import pytest
from fastapi import HTTPException
from final_evidence import CANONICAL_FINAL_ANALYSIS_RUNS, CANONICAL_FINAL_MANIFESTS, CORRECTED_ANALYSIS_VERSION, CORRECTED_ARTIFACT_SHA256, canonical_final_analysis_runs


def _run(rq_code: str):
    return SimpleNamespace(
        id=CANONICAL_FINAL_ANALYSIS_RUNS[rq_code],
        rq_code=rq_code,
        manifest_id=CANONICAL_FINAL_MANIFESTS[rq_code],
        status="COMPLETED",
        analysis_version=CORRECTED_ANALYSIS_VERSION,
        result_json={
            "evidence_class": "CONTROLLED",
            "analysis_scope": "FULL_POPULATION_SOURCE_PRECEDENCE",
            "analysis_artifact_identity": CORRECTED_ANALYSIS_VERSION,
            "artifact_sha256": CORRECTED_ARTIFACT_SHA256,
            "rq_key": "RQ7_PRIMARY" if rq_code == "RQ7" else rq_code,
            "metrics": {},
        },
    )


def test_canonical_analysis_selection_ignores_newer_or_legacy_rows():
    canonical_rows = [_run(rq) for rq in CANONICAL_FINAL_ANALYSIS_RUNS]
    extra = SimpleNamespace(id="newer-analysis", rq_code="RQ1", manifest_id="other", status="COMPLETED", result_json={"evidence_class": "CONTROLLED"})
    selected, error = canonical_final_analysis_runs([extra, *canonical_rows])
    assert error is None
    assert selected is not None
    assert {rq: str(row.id) for rq, row in selected.items()} == CANONICAL_FINAL_ANALYSIS_RUNS


def test_canonical_analysis_selection_fails_closed_when_a_record_is_missing():
    selected, error = canonical_final_analysis_runs([_run(rq) for rq in list(CANONICAL_FINAL_ANALYSIS_RUNS)[1:]])
    assert selected is None
    assert error == "Canonical final AnalysisRun records are missing."


def test_normal_startup_does_not_run_schema_or_sequence_maintenance(monkeypatch):
    calls: list[str] = []
    monkeypatch.delenv("JUDGELAB_RUN_MAINTENANCE_ON_STARTUP", raising=False)
    monkeypatch.setattr(main.Base.metadata, "create_all", lambda **_: calls.append("create_all"))
    monkeypatch.setattr(main, "resync_postgres_sequences", lambda *_: calls.append("resync"))

    async def exercise():
        async with main.lifespan(main.app):
            pass

    asyncio.run(exercise())
    assert calls == []


def test_public_leaderboard_is_read_only_when_artifacts_are_absent(monkeypatch, tmp_path):
    calls: list[str] = []
    monkeypatch.setattr(main, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(main, "compute_and_save_leaderboard", lambda *_: calls.append("write") or [])
    monkeypatch.setattr(main, "compute_leaderboard_read_only", lambda *_: [{"model": "historical-model"}])

    assert main.get_leaderboard("gpt-4o-mini") == [{"model": "historical-model"}]
    assert calls == []


def test_retired_legacy_mutation_and_macro_routes_are_not_exposed():
    paths = {route.path for route in main.app.routes}
    assert "/api/leaderboard/calculate" not in paths
    assert "/api/stats/macro-benchmark" not in paths


def test_health_is_unhealthy_and_sanitized_when_database_is_unavailable():
    class UnavailableDatabase:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("postgresql://user:secret@host:5432/private")

    response = main.health_check(UnavailableDatabase())
    assert response.status == "unhealthy"
    assert response.database == "unavailable"
    assert "secret" not in response.message
    assert "host" not in response.message


def test_legacy_bias_endpoint_uses_explicit_no_data_semantics():
    class EmptyResult:
        def fetchall(self):
            return []

    class EmptyDatabase:
        def execute(self, *_args, **_kwargs):
            return EmptyResult()

    payload = main.get_bias_stats(EmptyDatabase(), "gpt-4o-mini")
    assert payload["evidence_class"] == "LEGACY_EXPLORATORY"
    assert payload["status"] == "NO_DATA"
    assert payload["n"] == 0
    assert payload["position_data"]["position_a"] is None
    assert payload["format_bias"]["p_value"] is None


def test_live_provider_failure_is_sanitized_after_env_gate(monkeypatch):
    monkeypatch.setattr(main, "_validate_api_key_or_raise", lambda _model: None)
    monkeypatch.setattr(main, "call_judge", lambda **_: (_ for _ in ()).throw(RuntimeError("https://user:secret@example.invalid/provider")))
    request = main.EvaluateRequest(prompt="q", answer_a="a", answer_b="b")

    with pytest.raises(HTTPException) as error:
        main.evaluate_judge(request, object())

    assert error.value.status_code == 502
    assert error.value.detail == "Provider request failed."
    assert "secret" not in error.value.detail


def test_live_sandbox_env_gate_uses_the_explicit_local_flag(monkeypatch):
    monkeypatch.setenv("ENABLE_LIVE_SANDBOX_PROVIDER_CALLS", "true")

    assert main._live_sandbox_provider_calls_enabled() is True
    main._require_live_sandbox_enabled()

    monkeypatch.setenv("ENABLE_LIVE_SANDBOX_PROVIDER_CALLS", "false")
    assert main._live_sandbox_provider_calls_enabled() is False
    with pytest.raises(HTTPException) as error:
        main._require_live_sandbox_enabled()
    assert error.value.status_code == 403


def test_live_persistence_failure_is_sanitized_after_env_gate(monkeypatch):
    class FailingDatabase:
        def begin_nested(self):
            raise RuntimeError("postgresql://user:secret@example.invalid/private")

        def rollback(self):
            pass

    monkeypatch.setattr(main, "_validate_api_key_or_raise", lambda _model: None)
    monkeypatch.setattr(main, "call_judge", lambda **_: SimpleNamespace(verdict="A", reasoning="reasoning"))
    request = main.EvaluateRequest(prompt="q", answer_a="a", answer_b="b")

    with pytest.raises(HTTPException) as error:
        main.evaluate_judge(request, FailingDatabase())

    assert error.value.status_code == 500
    assert error.value.detail == "Unable to persist live evaluation."
    assert "secret" not in error.value.detail


def test_live_ensemble_persistence_failure_is_explicit(monkeypatch):
    class FailingDatabase:
        def begin_nested(self):
            raise RuntimeError("database unavailable")

        def rollback(self):
            pass

    monkeypatch.setattr(main, "_validate_api_key_or_raise", lambda _model: None)
    monkeypatch.setattr(main, "call_multi_judge_ensemble", lambda **_: SimpleNamespace(
        consensus_verdict="A",
        vote_counts={"A": 1, "B": 0, "TIE": 0},
        individual_results=[{"status": "success", "verdict": "A", "model_name": "gpt-4o-mini", "reasoning": "mocked"}],
        total_models=1,
        successful_models=1,
        total_input_tokens=10,
        total_output_tokens=1,
    ))

    payload = main.evaluate_ensemble(
        main.MultiJudgeEnsembleRequest(question="q", answer_a="a", answer_b="b", judge_models=["gpt-4o-mini"]),
        FailingDatabase(),
    )

    assert payload["consensus_verdict"] == "A"
    assert payload["persisted"] is False
