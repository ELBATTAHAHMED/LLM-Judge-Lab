"""Provider-free regression tests for final application safety boundaries."""
from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace

import main
from final_evidence import CANONICAL_FINAL_ANALYSIS_RUNS, CANONICAL_FINAL_MANIFESTS, canonical_final_analysis_runs


def _run(rq_code: str):
    return SimpleNamespace(
        id=CANONICAL_FINAL_ANALYSIS_RUNS[rq_code],
        rq_code=rq_code,
        manifest_id=CANONICAL_FINAL_MANIFESTS[rq_code],
        status="COMPLETED",
        result_json={"evidence_class": "CONTROLLED"},
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
    assert main.get_leaderboard("gpt-4o-mini") == []
    assert calls == []


def test_legacy_leaderboard_recalculation_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("JUDGELAB_ENABLE_LEGACY_LEADERBOARD_RECALCULATION", raising=False)
    request = main.CalculateLeaderboardRequest(judge_model="gpt-4o-mini")
    try:
        main.trigger_leaderboard_calculation(request, object())
    except main.HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("legacy recalculation was unexpectedly enabled")
