"""Regression coverage for the additive source-text remediation map."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from backend.historical.source_reconciliation import artifact_sha, build, load_raw_source  # noqa: E402
from backend.core.database import SessionLocal  # noqa: E402


def _artifact():
    with SessionLocal() as session:
        return build(session)


def test_source_text_reconciliation_is_complete_exact_text_keyed_and_deterministic():
    first, second = _artifact(), _artifact()
    result = first["reconstructed_result"]
    assert result == {"frozen_records": 1568, "source_exact": 1070, "source_correction_required": 498, "unresolved": 0, "vicuna_affected": 482, "non_vicuna_affected": 16}
    assert len(first["records"]) == len({row["frozen_record_key"] for row in first["records"]}) == 1568
    assert first["affected_record_keys"] == second["affected_record_keys"]
    assert artifact_sha(first) == artifact_sha(second)
    assert all(row["status"] in {"SOURCE_EXACT", "SOURCE_CORRECTION_REQUIRED"} for row in first["records"])
    assert all(row["frozen_answer_hashes"] != row["corrected_source_answer_hashes"] for row in first["records"] if row["status"] == "SOURCE_CORRECTION_REQUIRED")


def test_raw_source_index_contains_assistant_answers_only_and_never_db_order_identity():
    questions, answers, _labels, _sha = load_raw_source()
    assert len(questions) >= 160 and answers
    # Every indexed response was taken from an assistant position; the map key
    # is source question/turn/model rather than any database answer identifier.
    assert all(answer.question_id == key[0] and answer.turn == key[1] and answer.model == key[2] for key, answer in answers.items())
    artifact = _artifact()
    vicuna = [row for row in artifact["records"] if row["root_cause_category"] == "VICUNA_V13_OR_PROMPT_SHADOWING"]
    assert len(vicuna) == 482
    assert all(row["upstream_source_rows"][0]["dataset"] == "lmsys/mt_bench_human_judgments" for row in vicuna)
