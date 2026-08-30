"""Manual Live Sandbox records must not enter historical telemetry."""
from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.analysis.consistency import (
    compute_inter_judge_kappa,
    compute_self_preference_bias,
    fetch_decisions,
)
from backend.analysis.latent_quality import fetch_pairwise_results
from backend.analysis.neutralized_scores import fetch_decisions_with_lengths
from backend.core.controlled_models import AnalysisRun, ControlledRun
from backend.core.database import get_db
from backend.core.models import Answer, JudgeDecision, Prompt
from backend.main import app, get_bias_stats
import backend.main as main


ROOT = Path(__file__).resolve().parents[2]


def _seed_historical_pair(session):
    prompt = Prompt(text="shared telemetry prompt", category="historical")
    session.add(prompt)
    session.flush()
    answer_a = Answer(prompt_id=prompt.id, model_name="gpt-4o-mini", text="short answer", word_count=2)
    answer_b = Answer(prompt_id=prompt.id, model_name="anthropic/claude-3-haiku", text="longer answer text", word_count=3)
    session.add_all([answer_a, answer_b])
    session.flush()
    session.add_all([
        JudgeDecision(prompt_id=prompt.id, judge_model_name="gpt-4o-mini", answer_a_id=answer_a.id, answer_b_id=answer_b.id, position_a_id=answer_a.id, winner_id=answer_a.id, reasoning="historical"),
        JudgeDecision(prompt_id=prompt.id, judge_model_name="deepseek/deepseek-chat", answer_a_id=answer_a.id, answer_b_id=answer_b.id, position_a_id=answer_a.id, winner_id=answer_a.id, reasoning="historical"),
    ])


def test_mocked_live_trial_is_persisted_but_excluded_from_historical_telemetry(tmp_path, monkeypatch):
    """A same-text live trial cannot reuse historical prompts or alter aggregates."""
    path = tmp_path / "live-isolation.sqlite"
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{path.as_posix()}")
    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{path.as_posix()}", connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)

    def override_db():
        with Session() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with Session.begin() as session:
            _seed_historical_pair(session)

        with Session() as session:
            baseline_bias = get_bias_stats(session, judge_model="gpt-4o-mini")
            baseline_consistency = fetch_decisions(engine, "gpt-4o-mini")
            baseline_kappa = compute_inter_judge_kappa(engine, "gpt-4o-mini", "deepseek/deepseek-chat")
            baseline_self_preference = compute_self_preference_bias(session, "gpt-4o-mini")
            baseline_controlled = TestClient(app).get("/api/controlled/results").json()
            assert baseline_bias["n"] == len(baseline_consistency) == 1
            assert baseline_kappa["overlapping_trials"] == 1

        monkeypatch.setenv("ENABLE_LIVE_SANDBOX_PROVIDER_CALLS", "true")
        monkeypatch.setattr(main, "_validate_api_key_or_raise", lambda _model: None)
        monkeypatch.setattr(
            main,
            "call_judge",
            lambda **_: type("MockedLiveResult", (), {"verdict": "A", "reasoning": "mocked live result"})(),
        )

        response = TestClient(app).post(
            "/api/evaluate",
            json={
                "prompt": "shared telemetry prompt",
                "answer_a": "manual answer A",
                "answer_b": "manual answer B",
                "model_name": "gpt-4o-mini",
            },
        )

        assert response.status_code == 200
        with Session() as session:
            live_prompt = session.query(Prompt).filter_by(text="shared telemetry prompt", category="live").one()
            historical_prompt = session.query(Prompt).filter_by(text="shared telemetry prompt", category="historical").one()
            assert live_prompt.id != historical_prompt.id
            assert session.query(JudgeDecision).filter_by(prompt_id=live_prompt.id).count() == 1
            assert session.query(ControlledRun).count() == 0
            assert session.query(AnalysisRun).count() == 0

            assert get_bias_stats(session, judge_model="gpt-4o-mini") == baseline_bias
            assert compute_self_preference_bias(session, "gpt-4o-mini") == baseline_self_preference
            assert TestClient(app).get("/api/controlled/results").json() == baseline_controlled

        assert fetch_decisions(engine, "gpt-4o-mini").equals(baseline_consistency)
        assert compute_inter_judge_kappa(engine, "gpt-4o-mini", "deepseek/deepseek-chat") == baseline_kappa
        assert len(fetch_pairwise_results(engine, "gpt-4o-mini")) == 1
        assert len(fetch_decisions_with_lengths(engine, "gpt-4o-mini")) == 1
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
