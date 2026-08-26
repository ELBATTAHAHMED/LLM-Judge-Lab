"""OpenRouter routing is fail-closed and fixture-verifiable without HTTP."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from backend.evaluation.engine import EvaluationRequest
from backend.evaluation.providers import ProviderExecutionGate, adapter_for_judge
from backend.core.model_registry import Provider


def request():
    return EvaluationRequest(question="q", answer_a="a", answer_b="b", judge_name="deepseek/deepseek-chat", provider=Provider.OPENROUTER, requested_model="deepseek/deepseek-chat", temperature=0.7, top_p=1.0, seed=None, prompt_template_version="controlled-judge-pairwise-v1", experiment_id="00000000-0000-0000-0000-000000000001", controlled_unit_id="00000000-0000-0000-0000-000000000002", repetition_index=3, pass_number=1, original_answer_a_id=1, original_answer_b_id=2, presented_answer_a_id=1, presented_answer_b_id=2)


def gate():
    return ProviderExecutionGate(mode="REAL", authorization_token="fixture", verified_pricing_version="fixture", max_provider_calls=1, max_input_tokens=1, max_output_tokens=1, max_usd=1)


def test_unverified_openrouter_route_fails_before_fixture_transport(monkeypatch):
    import backend.evaluation.providers as providers
    calls = []
    monkeypatch.setattr(providers, "openrouter_request_controls", lambda _judge: (_ for _ in ()).throw(ValueError("not officially verified")))
    adapter = adapter_for_judge("deepseek/deepseek-chat", gate=gate(), transport=lambda *args: calls.append(args) or {})
    with pytest.raises(ValueError, match="not officially verified"):
        adapter.evaluate(request())
    assert calls == []


def test_verified_route_controls_and_router_metadata_are_required(monkeypatch):
    import backend.evaluation.providers as providers
    captured = {}
    monkeypatch.setattr(providers, "openrouter_request_controls", lambda _judge: ({"X-OpenRouter-Metadata": "enabled"}, {"provider": {"order": ["fixture-upstream"], "only": ["fixture-upstream"], "allow_fallbacks": False, "require_parameters": True}}))
    monkeypatch.setattr(providers, "validate_router_response", lambda **kwargs: captured.setdefault("validated", kwargs))
    def transport(_endpoint, headers, payload):
        captured.update(headers=headers, payload=payload)
        return {"id": "router-fixture", "model": "deepseek/deepseek-chat", "provider": {"provider": "fixture-upstream"}, "choices": [{"message": {"content": '{"verdict":"ANSWER_A","criteria_scores":{"correctness":5,"relevance":5,"completeness":5,"clarity":5,"safety":5},"confidence":0.5,"explanation":"fixture"}'}}]}
    response = adapter_for_judge("deepseek/deepseek-chat", gate=gate(), transport=transport).evaluate(request())
    assert captured["headers"]["X-OpenRouter-Metadata"] == "enabled"
    assert captured["payload"]["provider"]["allow_fallbacks"] is False
    assert captured["payload"]["provider"]["only"] == ["fixture-upstream"]
    assert captured["payload"]["provider"]["require_parameters"] is True
    assert captured["validated"]["judge_name"] == "deepseek/deepseek-chat"
    assert response.provider_response_id == "router-fixture"
