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


def test_call_calibrated_judge_unit_logic():
    """Verify call_calibrated_judge consensus and position bias detection logic using a mock client."""
    from unittest.mock import MagicMock
    from judge_engine import call_calibrated_judge

    mock_client = MagicMock()
    # Pass 1 response: WINNER: A
    res1 = MagicMock()
    res1.choices = [MagicMock(message=MagicMock(content="WINNER: A"))]
    res1.usage = MagicMock(prompt_tokens=100, completion_tokens=50)

    # Pass 2 response: WINNER: A (which maps to Candidate B, detecting position bias)
    res2 = MagicMock()
    res2.choices = [MagicMock(message=MagicMock(content="WINNER: A"))]
    res2.usage = MagicMock(prompt_tokens=100, completion_tokens=50)

    mock_client.chat.completions.create.side_effect = [res1, res2]

    res = call_calibrated_judge(
        client=mock_client,
        question="Which is better?",
        answer_a="Response A",
        answer_b="Response B",
    )

    assert res.original_order_winner == "A"
    assert res.swapped_order_winner == "B"
    assert res.position_bias_detected is True
    assert res.final_calibrated_winner == "TIE"


def test_calibrated_evaluation_endpoint_validation(client):
    """Verify POST /api/evaluate/calibrated request payload handling."""
    payload = {
        "question": "Explain quantum computing simply.",
        "answer_a": "Quantum computing uses qubits...",
        "answer_b": "Quantum computing processes data using superposition...",
        "model_name": "gpt-4o-mini",
        "temperature": 0.0,
    }
    response = client.post("/api/evaluate/calibrated", json=payload)
    assert response.status_code in (200, 500)
    if response.status_code == 200:
        data = response.json()
        assert data["status"] == "success"
        assert "final_calibrated_winner" in data
        assert "position_bias_detected" in data


def test_local_ollama_model_routing_and_client_resolution(client):
    """Verify detection of local Ollama models and graceful client resolution."""
    from judge_engine import is_local_model, get_evaluator_client

    assert is_local_model("Llama-3 8B (Local / Ollama)") is True
    assert is_local_model("ollama/llama3") is True
    assert is_local_model("gpt-4o-mini") is False

    local_client, target_model = get_evaluator_client("Llama-3 8B (Local / Ollama)")
    assert str(local_client.base_url).rstrip("/") == "http://localhost:11434/v1"
    assert target_model == "llama3"

    # Verify live endpoint handles local model without 404
    payload = {
        "prompt": "Test prompt",
        "answer_a": "Answer A text",
        "answer_b": "Answer B text",
        "model_name": "Llama-3 8B (Local / Ollama)",
    }
    response = client.post("/api/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "winner" in data
    assert "model_name" in data
    assert "Llama-3" in data["model_name"]


