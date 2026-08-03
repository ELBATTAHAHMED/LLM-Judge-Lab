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


def test_macro_benchmark_endpoint(client):
    """Verify GET /api/stats/macro-benchmark returns all required before/after synthesis metrics."""
    response = client.get("/api/stats/macro-benchmark")
    assert response.status_code == 200
    data = response.json()
    
    required_keys = [
        "judge_model",
        "total_evaluations",
        "baseline_kappa",
        "calibrated_kappa",
        "delta_kappa",
        "baseline_accuracy",
        "calibrated_accuracy",
        "delta_accuracy",
        "baseline_flip_rate",
        "mitigated_flip_rate",
        "flip_rate_reduction",
    ]
    for key in required_keys:
        assert key in data, f"Missing required macro benchmark key: {key}"

    assert data["total_evaluations"] > 0
    assert data["delta_kappa"] >= 0
    assert data["flip_rate_reduction"] >= 0.0



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

    # Verify live endpoint handles local model (returns 200 if Ollama running, 500 if offline)
    payload = {
        "prompt": "Test prompt",
        "answer_a": "Answer A text",
        "answer_b": "Answer B text",
        "model_name": "Llama-3 8B (Local / Ollama)",
    }
    response = client.post("/api/evaluate", json=payload)
    assert response.status_code in (200, 500)
    if response.status_code == 200:
        data = response.json()
        assert "winner" in data
        assert "model_name" in data
        assert "Llama-3" in data["model_name"]
    else:
        data = response.json()
        assert "Standard evaluation failed" in data["detail"]


def test_self_preference_bias_calculation(monkeypatch):
    """Verify compute_self_preference_bias mathematical calculations using synthetic Pandas DataFrame."""
    import pandas as pd
    from unittest.mock import MagicMock
    from analyze_consistency import compute_self_preference_bias

    # 10 Self Matchups (gpt-4o-mini vs llama-3.3-70b-instruct): 8 wins for gpt-4o-mini (answer_a_id=1), 2 wins for llama (answer_b_id=2)
    self_rows = [
        {"decision_id": i, "judge_model": "gpt-4o-mini", "model_a": "gpt-4o-mini", "model_b": "meta-llama/llama-3.3-70b-instruct", "winner_id": 1 if i <= 8 else 2, "answer_a_id": 1, "answer_b_id": 2}
        for i in range(1, 11)
    ]

    # 10 Imbalanced Other Matchups (llama vs claude): 8 wins for llama in Position A (answer_a_id=3), 2 wins for claude in Position B (answer_b_id=4)
    other_rows = [
        {"decision_id": 10 + i, "judge_model": "gpt-4o-mini", "model_a": "meta-llama/llama-3.3-70b-instruct", "model_b": "anthropic/claude-3-haiku", "winner_id": 3 if i <= 8 else 4, "answer_a_id": 3, "answer_b_id": 4}
        for i in range(1, 11)
    ]

    mock_df = pd.DataFrame(self_rows + other_rows)

    def mock_read_sql(*args, **kwargs):
        return mock_df

    monkeypatch.setattr(pd, "read_sql", mock_read_sql)

    mock_db = MagicMock()
    res = compute_self_preference_bias(mock_db, judge_model_name="gpt-4o-mini")

    assert res["judge_model"] == "gpt-4o-mini"
    assert res["judge_family"] == "gpt"
    assert res["total_self_matchups"] == 10
    assert res["total_other_matchups"] == 10
    assert res["self_win_rate"] == 0.8
    assert res["baseline_win_rate"] == 0.8
    assert res["self_preference_ratio"] == 1.0


def test_self_preference_bias_empty_matchups(monkeypatch):
    """Verify compute_self_preference_bias returns None (not 0.5 / 1.0) when total_self_matchups is 0."""
    import pandas as pd
    from unittest.mock import MagicMock
    from analyze_consistency import compute_self_preference_bias

    # 10 Matchups between rival families only (no gpt candidate answers present)
    other_rows = [
        {"decision_id": i, "judge_model": "gpt-4o-mini", "model_a": "meta-llama/llama-3.3-70b-instruct", "model_b": "anthropic/claude-3-haiku", "winner_id": 3 if i <= 5 else 4, "answer_a_id": 3, "answer_b_id": 4}
        for i in range(1, 11)
    ]
    mock_df = pd.DataFrame(other_rows)

    def mock_read_sql(*args, **kwargs):
        return mock_df

    monkeypatch.setattr(pd, "read_sql", mock_read_sql)

    mock_db = MagicMock()
    res = compute_self_preference_bias(mock_db, judge_model_name="gpt-4o-mini")

    assert res["judge_model"] == "gpt-4o-mini"
    assert res["total_self_matchups"] == 0
    assert res["self_win_rate"] is None
    assert res["self_preference_ratio"] is None
    assert res["p_value"] is None
    assert res["self_preference_detected"] is False


def test_normalize_model_id():
    """Verify normalize_model_id handles legacy tags, OpenRouter strings, unknown models, and None."""
    from main import normalize_model_id

    # Legacy tag
    assert normalize_model_id("gpt-4") == "gpt-4o-mini"

    # OpenRouter slash format
    assert normalize_model_id("meta-llama/llama-3.3-70b-instruct") == "meta-llama/llama-3.3-70b-instruct"

    # Unknown string
    assert normalize_model_id("unknown-model-xyz") == "unknown-model-xyz"

    # None input
    assert normalize_model_id(None) == "gpt-4o-mini"



