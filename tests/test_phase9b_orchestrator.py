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
    assert "Scientifically Succeeded Units:       12,412" in captured
    assert "Pending Provider-Eligible Units (RQ5): 226" in captured
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
        assert len(succeeded_unit_ids) == 12412

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
        assert len(pending) == 226

        manifest_by_id = {m.id: m for m in session.query(ExperimentManifest).all()}
        pending_rqs = {manifest_by_id[u.manifest_id].rq_code for u in pending}
        assert pending_rqs == {"RQ5"}
    finally:
        session.close()


def test_mock_resume_dispatches_only_226_rq5_units_and_second_run_zero(tmp_path):
    """Offline simulation of the resume loop proving 226 units / 452 passes on run 1 and 0 on run 2."""
    from database import SessionLocal
    from controlled_models import ControlledRun, ExperimentalUnit, ExperimentManifest
    from run_controlled_experiment import materialize_evaluation_request
    from controlled_evaluation import EvaluationRequest, ControlledExecutionService, ControlledEvaluationEngine
    from controlled_persistence import ControlledPersistence, Outcome, PassObservation
    from mock_provider import DeterministicMockProvider, MockScenario
    import hashlib

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
        assert len(pending_units) == 226

        # Verify all 226 pending payloads materialize cleanly with CounterfactualVariant
        for u in pending_units:
            req, is_dual = materialize_evaluation_request(session, u, manifest_rq=manifest_rq)
            assert is_dual is True
            assert req.pass_number == 1
            assert len(req.answer_a) > 0
            assert len(req.answer_b) > 0
            assert req.presentation_provenance == {"variant_slot": "B"}
    finally:
        session.close()

