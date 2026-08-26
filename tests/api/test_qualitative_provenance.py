from __future__ import annotations

from pathlib import Path

import pandas as pd

import main


class _Result:
    def __init__(self, rows): self.rows = rows
    def fetchall(self): return self.rows


class _Connection:
    def __init__(self, prompts, answers): self.prompts, self.answers = prompts, answers
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def execute(self, statement, _params):
        return _Result(self.prompts if "FROM prompts" in str(statement) else self.answers)


class _Engine:
    def __init__(self, prompts, answers): self.prompts, self.answers = prompts, answers
    def connect(self): return _Connection(self.prompts, self.answers)


def _records(monkeypatch, answers):
    monkeypatch.setattr(main.pd, "read_csv", lambda _: pd.DataFrame([{"prompt_id": 81, "model_names": "gpt-3.5-turbo vs claude-v1", "reasoning_text": "r", "word_count_diff": 0, "human_winner": "A", "ai_winner": "A"}]))
    import backend.core.database as database
    monkeypatch.setattr(database, "engine", _Engine([(81, "prompt")], answers))
    return main.get_qualitative_bucket("verbosity", judge_model="gpt-4o-mini")[0]


def test_qualitative_answers_resolve_by_declared_model_not_database_order(monkeypatch):
    row = _records(monkeypatch, [(9, 81, "gpt-4", "wrong"), (4, 81, "claude-v1", "claude"), (2, 81, "gpt-3.5-turbo", "gpt35")])
    assert row["provenance_status"] == "VERIFIED"
    assert (row["answer_a_model"], row["answer_a_text"], row["answer_b_model"], row["answer_b_text"]) == ("gpt-3.5-turbo", "gpt35", "claude-v1", "claude")


def test_qualitative_ambiguous_or_missing_provenance_fails_closed(monkeypatch):
    for answers in ([(1, 81, "gpt-3.5-turbo", "a"), (2, 81, "gpt-3.5-turbo", "duplicate"), (3, 81, "claude-v1", "b")], [(1, 81, "gpt-3.5-turbo", "a")]):
        row = _records(monkeypatch, answers)
        assert row["provenance_status"] == "UNAVAILABLE"
        assert "answer_a_text" not in row and "answer_b_text" not in row


def test_qualitative_ui_has_no_fabricated_answer_fallbacks():
    source = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "QualitativeExplorerPage.tsx").read_text(encoding="utf-8")
    assert "Provenance unavailable; answer text is not displayed." in source
    assert "Detailed candidate response grounded" not in source
