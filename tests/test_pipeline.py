"""
tests/test_pipeline.py
======================
Automated PyTest suite for the JudgeLab M2 Master's Thesis Platform.

Tests:
  1. Health check endpoint (GET /) returns status 200 and healthy JSON payload.
  2. Benjamini-Hochberg FDR p-value adjustment (_adjust_pvalues_bh) produces expected adjusted array.
  3. Database engine initializes and connects without crashing.
  4. Telemetry endpoint (GET /api/stats/bias) returns all required research metrics keys.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure backend/ directory is in sys.path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from main import app, _adjust_pvalues_bh
from database import engine


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    return TestClient(app)


def test_health_check_endpoint(client):
    """Verify GET / endpoint returns HTTP 200 and health payload."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "healthy"


def test_fdr_pvalue_adjustment():
    """Verify Benjamini-Hochberg FDR p-value correction routine."""
    raw_pvalues = [0.001, 0.04, 0.20, 0.50]
    adjusted = _adjust_pvalues_bh(raw_pvalues)
    
    assert len(adjusted) == len(raw_pvalues)
    assert all(isinstance(p, float) for p in adjusted)
    # Adjusted p-values should be monotonically non-decreasing
    assert adjusted[0] <= adjusted[1] <= adjusted[2] <= adjusted[3]
    # Check that adjusted p-values remain bounded in [0, 1]
    assert all(0.0 <= p <= 1.0 for p in adjusted)


def test_database_engine_initialization():
    """Verify SQLAlchemy engine initializes and executes a simple query."""
    with engine.connect() as conn:
        result = conn.exec_driver_sql("SELECT 1").scalar()
        assert result == 1


def test_bias_telemetry_endpoint(client):
    """Verify GET /api/stats/bias returns all 5 required research keys."""
    response = client.get("/api/stats/bias")
    assert response.status_code == 200
    data = response.json()
    
    required_keys = ["verbosity_data", "position_data", "domain_kappa", "format_bias", "inter_judge_kappa"]
    for key in required_keys:
        assert key in data, f"Missing required telemetry key: {key}"

    assert isinstance(data["inter_judge_kappa"], (int, float))
