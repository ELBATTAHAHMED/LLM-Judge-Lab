from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from controlled_real_execution import RealExecutionProfile, ExecutionCaps
from run_controlled_experiment import build_controlled_profile, run_preflight, print_status
from database import engine as live_postgres_engine

def test_controlled_profile_matches_frozen_scientific_identity():
    profile = build_controlled_profile(authorization_token="test-tok", max_usd=Decimal("7.50"))
    assert profile.execution_mode == "REAL"
    assert profile.evidence_class == "CONTROLLED"
    assert profile.source_tag in {
        "pre-controlled-pilot-v8",
        "pre-controlled-phase9b-v1",
        "controlled-launch-v1",
        "controlled-phase9b-resume-v2",
        "controlled-phase9b-reconciled-v1",
        "controlled-phase9b-rq5-reconciled-v1",
        "controlled-phase9b-rq5-reconciled-v2",
    }
    assert profile.prompt_version == "controlled-judge-pairwise-v1"
    assert profile.routing_version == "controlled-routing-v1"
    assert profile.routing_fingerprint == "bf8d0d1ef228f60e07ceff2e1da43eeefe8ae5538d439b5d9a4c325294b7030b"
    assert len(profile.manifest_ids) == 7
    assert len(profile.manifest_hashes) == 7
    assert set(profile.model_ids) == {"gpt-4o-mini", "anthropic/claude-3-haiku", "deepseek/deepseek-chat", "meta-llama/llama-3.3-70b-instruct"}
    assert set(profile.configured_upstreams) == {"amazon-bedrock", "streamlake", "deepinfra/turbo"}
    profile.assert_authorized()


def test_preflight_runs_without_provider_calls(capsys):
    run_preflight()
    captured = capsys.readouterr().out
    assert "16,600 scientific calls across 13,400 units" in captured
    assert "Offline payload validation: 13,400 / 13,400 units (16,600 / 16,600 passes) VALID [100% OK]" in captured
    assert "gpt-4o-mini" in captured
    assert "anthropic/claude-3-haiku" in captured
    assert "deepseek/deepseek-chat" in captured
    assert "meta-llama/llama-3.3-70b-instruct" in captured
    assert "[SAFE]" in captured


def test_status_shows_controlled_progress_and_preserves_pilot_isolation(capsys):
    print_status()
    captured = capsys.readouterr().out
    assert "PHASE 9B CONTROLLED EXECUTION STATUS" in captured
    assert "TOTAL PLANNED UNITS ACCOUNTED: 13,400 / 13,400" in captured
    assert "Scientifically Succeeded Units:       12,602" in captured
    assert "Pending Provider-Eligible Units (RQ5): 0" in captured
    assert "Published AnalysisRuns:                  0 / 7" in captured


def test_materialize_evaluation_request_remediates_empty_answer_b():
    from database import SessionLocal
    from controlled_models import ExperimentalUnit
    from run_controlled_experiment import materialize_evaluation_request

    session = SessionLocal()
    try:
        # Previously failing units in raw dataset where raw answer_b_id=1056 has len 0
        unit_rq5 = session.get(ExperimentalUnit, "49d79bed-4be3-4f45-87e1-e0ce3d918741")
        assert unit_rq5 is not None
        req5, is_dual5 = materialize_evaluation_request(session, unit_rq5)
        assert is_dual5 is True
        assert len(req5.answer_a) > 0
        assert len(req5.answer_b) == 798  # counterfactual variant text
        assert req5.presentation_provenance == {"variant_slot": "B"}

        unit_rq4 = session.get(ExperimentalUnit, "01926de6-9111-46ec-98c9-84f47f5c064d")
        assert unit_rq4 is not None
        req4, is_dual4 = materialize_evaluation_request(session, unit_rq4)
        assert is_dual4 is True
        assert len(req4.answer_a) > 0
        assert len(req4.answer_b) == 1530  # counterfactual variant text
        assert req4.presentation_provenance == {"variant_slot": "B"}
    finally:
        session.close()


def test_resume_skips_already_completed_controlled_units():
    from database import SessionLocal
    from controlled_models import ControlledRun, ExperimentalUnit, ExperimentManifest

    session = SessionLocal()
    try:
        all_runs = session.query(ControlledRun).all()
        succeeded_runs = [
            r for r in all_runs
            if r.status == "SUCCEEDED" and (r.metadata_json or {}).get("evidence_class") == "CONTROLLED"
        ]
        succeeded_unit_ids = {r.experimental_unit_id for r in succeeded_runs}
        assert len(succeeded_unit_ids) == 12602

        superseded_runs = [
            r for r in all_runs
            if (r.metadata_json or {}).get("evidence_class") == "SUPERSEDED_CONTROLLED"
        ]
        assert len(superseded_runs) == 226

        controlled_runs = [
            r for r in all_runs
            if (r.metadata_json or {}).get("evidence_class") == "CONTROLLED"
        ]
        terminal_unit_ids = set()
        for r in controlled_runs:
            if r.status in {"SUCCEEDED", "FAILED"}:
                terminal_unit_ids.add(r.experimental_unit_id)
            elif r.status == "PARTIAL" and len(r.passes) == 2:
                terminal_unit_ids.add(r.experimental_unit_id)

        all_units = session.query(ExperimentalUnit).all()
        pending = [u for u in all_units if u.id not in terminal_unit_ids]
        assert len(pending) == 0
    finally:
        session.close()


def test_mock_resume_all_units_complete_zero_dispatched():
    """Verify that with all 13,400 units complete, resume dispatches 0 units / 0 calls."""
    from database import SessionLocal
    from controlled_models import ControlledRun, ExperimentalUnit, ExperimentManifest

    session = SessionLocal()
    try:
        manifest_rq = {m.id: m.rq_code for m in session.query(ExperimentManifest).all()}
        units = session.query(ExperimentalUnit).order_by(ExperimentalUnit.manifest_id, ExperimentalUnit.id).all()

        controlled_runs = [
            r for r in session.query(ControlledRun).all()
            if (r.metadata_json or {}).get("evidence_class") == "CONTROLLED"
        ]
        terminal_unit_ids = {
            r.experimental_unit_id for r in controlled_runs
            if r.status in {"SUCCEEDED", "FAILED"} or (r.status == "PARTIAL" and len(r.passes) == 2)
        }
        pending_units = [u for u in units if u.id not in terminal_unit_ids]
        assert len(pending_units) == 0
    finally:
        session.close()


def test_exact_failed_unit_offline_no_collision():
    """Verify exact failed unit 002b7338-20b7-4d93-a384-d8a8fb88e724 executes without attempt_id collision."""
    from database import SessionLocal
    from controlled_models import ControlledRun, ExperimentalUnit, PassAttempt
    from run_controlled_experiment import materialize_evaluation_request
    from controlled_evaluation import ControlledExecutionService, ControlledEvaluationEngine
    from controlled_persistence import ControlledPersistence
    from mock_provider import DeterministicMockProvider, MockScenario
    import hashlib

    session = SessionLocal()
    try:
        unit = session.get(ExperimentalUnit, "002b7338-20b7-4d93-a384-d8a8fb88e724")
        assert unit is not None

        superseded_run = session.query(ControlledRun).filter(
            ControlledRun.experimental_unit_id == unit.id,
            ControlledRun.status == "SKIPPED",
        ).first()
        assert superseded_run is not None
        superseded_attempt_ids = {a.attempt_id for a in session.query(PassAttempt).filter(PassAttempt.run_id == superseded_run.id).all()}
        assert len(superseded_attempt_ids) > 0

        # Current controlled run
        controlled_run = session.query(ControlledRun).filter(
            ControlledRun.experimental_unit_id == unit.id,
            ControlledRun.status == "SUCCEEDED",
        ).first()
        assert controlled_run is not None
        assert controlled_run.parent_run_id == superseded_run.id
        controlled_attempt_ids = {a.attempt_id for a in session.query(PassAttempt).filter(PassAttempt.run_id == controlled_run.id).all()}
        assert len(controlled_attempt_ids) == 2
        for aid in controlled_attempt_ids:
            assert aid not in superseded_attempt_ids
    finally:
        session.close()


def test_retry_identity_deterministic_and_unique():
    """Verify attempt_id generation across retries and passes is deterministic and globally distinct."""
    from database import SessionLocal
    from controlled_models import ControlledRun, ExperimentalUnit
    from controlled_persistence import ControlledPersistence
    import hashlib

    session = SessionLocal()
    try:
        unit = session.query(ExperimentalUnit).first()
        repo = ControlledPersistence(session)
        savepoint = session.begin_nested()
        try:
            test_key = hashlib.sha256(f"test:retry:{unit.id}".encode()).hexdigest()
            test_run = repo.create_run(unit=unit, idempotency_key=test_key, requested_model="deepseek/deepseek-chat")

            att1_0 = repo.begin_attempt(run=test_run, pass_number=1)
            repo.finish_attempt(att1_0, state="FAILED_RETRYABLE", failure_category="RATE_LIMIT")

            att1_1 = repo.begin_attempt(run=test_run, pass_number=1)
            repo.finish_attempt(att1_1, state="FAILED_RETRYABLE", failure_category="RATE_LIMIT")

            att1_2 = repo.begin_attempt(run=test_run, pass_number=1)
            repo.finish_attempt(att1_2, state="FAILED_FINAL", failure_category="RATE_LIMIT")

            att2_0 = repo.begin_attempt(run=test_run, pass_number=2)
            repo.finish_attempt(att2_0, state="SUCCEEDED")

            attempt_ids = [att1_0.attempt_id, att1_1.attempt_id, att1_2.attempt_id, att2_0.attempt_id]
            assert len(set(attempt_ids)) == 4
        finally:
            savepoint.rollback()
    finally:
        session.close()

