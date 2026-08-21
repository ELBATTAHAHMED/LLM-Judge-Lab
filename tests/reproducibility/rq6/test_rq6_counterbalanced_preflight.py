"""Provider-free validation of the new RQ6 remediation design lineage."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from experiment_planning import PairRecord
from controlled_prompt import build_messages
from rq6_counterbalanced_preflight import HUMAN_OTHER, HUMAN_SELF, materialize


def pair(index: int, answer_a_model: str, answer_b_model: str, label: str) -> PairRecord:
    return PairRecord(
        index, index, index * 10 + 1, index * 10 + 2, "question", "answer", answer_a_model, answer_b_model,
        "reasoning", label,
    )


def test_counterbalanced_rq6_design_is_deterministic_blind_and_exactly_balanced():
    # Each judge has a same-family and other-family human-reference stratum in
    # one exact category × competing-family match stratum.  No provider exists
    # in this test path.
    pairs = [
        pair(1, "gpt-4", "claude-v1", "ANSWER_A"), pair(2, "gpt-4", "claude-v1", "ANSWER_B"),
        pair(3, "claude-v1", "llama-13b", "ANSWER_A"), pair(4, "claude-v1", "llama-13b", "ANSWER_B"),
        pair(5, "llama-13b", "gpt-3.5-turbo", "ANSWER_A"), pair(6, "llama-13b", "gpt-3.5-turbo", "ANSWER_B"),
        pair(7, "gpt-4", "claude-v1", "TIE"),  # definitive human strata are required
    ]
    first = materialize(pairs, {row.prompt_id: "Question" for row in pairs})
    second = materialize(pairs, {row.prompt_id: "Question" for row in pairs})

    assert first["manifest_sha256"] == second["manifest_sha256"]
    assert first["source_identity_blinded_to_judge"] is True
    assert first["validation"]["ok"] is True
    assert first["validation"]["all_matching_strata_exactly_balanced"] is True
    assert first["validation"]["presentation_proof"] == {"same_family_in_A": first["validation"]["selected_units"], "same_family_in_B": first["validation"]["selected_units"]}
    assert "deepseek/deepseek-chat" in first["excluded_configured_judges"]
    assert first["validation"]["planned_pass_slots"] == 2 * first["validation"]["selected_units"]
    for unit in first["units"]:
        assert [entry["presentation_order"] for entry in unit["passes"]] == ["AB", "BA"]
        assert unit["passes"][0]["presented_answer_a_id"] == unit["original_answer_ids"][0]
        assert unit["passes"][1]["presented_answer_a_id"] == unit["original_answer_ids"][1]
    for counts in first["validation"]["human_reference_balance_by_judge"].values():
        assert counts[HUMAN_SELF] == counts[HUMAN_OTHER]


def test_controlled_prompt_does_not_disclose_source_identity():
    messages = build_messages(question="Question", answer_a="Answer A", answer_b="Answer B")
    rendered = "\n".join(message["content"] for message in messages).lower()
    assert "source family" not in rendered
    assert "model source" not in rendered
    assert "do not infer authorship" in rendered
