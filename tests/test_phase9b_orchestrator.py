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
    assert profile.source_tag in {"pre-controlled-pilot-v8", "controlled-launch-v1"}
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
    assert "gpt-4o-mini" in captured
    assert "anthropic/claude-3-haiku" in captured
    assert "deepseek/deepseek-chat" in captured
    assert "meta-llama/llama-3.3-70b-instruct" in captured
    assert "[SAFE]" in captured

def test_status_shows_zero_controlled_runs_and_preserves_pilot_isolation(capsys):
    print_status()
    captured = capsys.readouterr().out
    assert "TOTAL CONTROLLED PROGRESS: 0 / 13,400 units (0 / 16,600 passes)" in captured
    assert "Published AnalysisRuns: 0 / 7" in captured
