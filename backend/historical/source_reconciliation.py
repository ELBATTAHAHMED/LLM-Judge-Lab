"""Build the additive source-text reconciliation map without provider access.

Historical answer IDs identify the frozen record only.  Corrected answers are
always selected from raw LMSYS assistant turns using source question/model/text
identity, never from database ordering.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from backend.core.controlled_models import ExperimentalUnit
from backend.core.models import Answer, Prompt


ROOT = Path(__file__).resolve().parent.parent.parent
RAW = ROOT / "data" / "human_judgment.jsonl"
OUTPUT = ROOT / "evidence" / "remediation" / "source_text_reconciliation_v1.json"
IDENTITY = "source-text-reconciliation-v1"
POLICY = "raw-human-row-source-text-v2"


class ReconciliationError(RuntimeError):
    pass


def sha(value: str | bytes) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def stable_sha(value: Any) -> str:
    return sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def model_name(value: str) -> str:
    return {"vicuna-13b-v1.2": "vicuna-13b"}.get(value, value)


@dataclass(frozen=True)
class SourceAnswer:
    question_id: int
    turn: int
    model: str
    text: str

    @property
    def text_hash(self) -> str:
        return sha(self.text)


@dataclass(frozen=True)
class FrozenRecord:
    prompt_id: int
    answer_a_id: int
    answer_b_id: int
    answer_a_model: str
    answer_b_model: str
    answer_a_text: str
    answer_b_text: str
    human_label: str
    prompt_text: str

    @property
    def key(self) -> str:
        return sha("|".join(("controlled-frozen-record-v1", str(self.prompt_id), str(self.answer_a_id), str(self.answer_b_id), self.answer_a_model, self.answer_b_model, sha(self.answer_a_text), sha(self.answer_b_text), self.human_label)))


def load_raw_source() -> tuple[dict[str, int], dict[tuple[int, int, str], SourceAnswer], dict[tuple[int, str, str, str], set[int]], str]:
    questions: dict[str, int] = {}
    answers: dict[tuple[int, int, str], SourceAnswer] = {}
    labels: dict[tuple[int, str, str, str], set[int]] = defaultdict(set)
    raw_bytes = RAW.read_bytes()
    for line in raw_bytes.splitlines():
        row = json.loads(line)
        qid, turn = int(row["question_id"]), int(row["turn"])
        label = {"model_a": "ANSWER_A", "model_b": "ANSWER_B", "tie": "TIE"}.get(row["winner"])
        if label is None:
            raise ReconciliationError("unknown upstream winner")
        first_model, second_model = model_name(row["model_a"]), model_name(row["model_b"])
        labels[(qid, first_model, second_model, label)].add(turn)
        for side in ("a", "b"):
            messages = row[f"conversation_{side}"]
            source_model = model_name(row[f"model_{side}"])
            # Only assistant messages enter the answer index. This prevents a
            # legacy user-prompt row from ever satisfying a corrected answer.
            answer = SourceAnswer(qid, turn, source_model, messages[2 * turn - 1]["content"])
            previous = answers.setdefault((qid, turn, source_model), answer)
            if previous.text != answer.text:
                raise ReconciliationError("raw source has inconsistent model answer text")
            for prompt in (messages[2 * turn - 2]["content"],):
                mapped = questions.setdefault(prompt, qid)
                if mapped != qid:
                    raise ReconciliationError("raw question maps to multiple IDs")
            if turn == 2:
                combined = messages[0]["content"] + "\n\n[Follow-up Question]: " + messages[2]["content"]
                mapped = questions.setdefault(combined, qid)
                if mapped != qid:
                    raise ReconciliationError("combined raw question maps to multiple IDs")
    return questions, answers, labels, sha(raw_bytes)


def frozen_records(session: Session) -> list[FrozenRecord]:
    a, b = aliased(Answer), aliased(Answer)
    rows = session.execute(
        select(ExperimentalUnit.prompt_id, ExperimentalUnit.answer_a_id, ExperimentalUnit.answer_b_id, ExperimentalUnit.answer_a_author_id, ExperimentalUnit.answer_b_author_id, ExperimentalUnit.human_label, Prompt.text, a.text, a.model_name, b.text, b.model_name)
        .join(Prompt, Prompt.id == ExperimentalUnit.prompt_id)
        .join(a, a.id == ExperimentalUnit.answer_a_id)
        .join(b, b.id == ExperimentalUnit.answer_b_id)
    )
    by_identity: dict[tuple[int, int, int, str], FrozenRecord] = {}
    for prompt_id, a_id, b_id, a_author, b_author, label, prompt, a_text, a_model, b_text, b_model in rows:
        record = FrozenRecord(prompt_id, a_id, b_id, model_name(a_author or a_model), model_name(b_author or b_model), a_text, b_text, label or "", prompt)
        key = (prompt_id, a_id, b_id, label or "")
        previous = by_identity.setdefault(key, record)
        if previous != record:
            raise ReconciliationError("frozen unit metadata disagrees across RQ reuse")
    result = sorted(by_identity.values(), key=lambda record: record.key)
    if len(result) != 1568 or len({record.key for record in result}) != 1568:
        raise ReconciliationError(f"expected exactly 1568 unique frozen records, found {len(result)}")
    return result


def resolve_turn(record: FrozenRecord, qid: int, answers: dict[tuple[int, int, str], SourceAnswer], labels: dict[tuple[int, str, str, str], set[int]]) -> tuple[int, str]:
    candidates = {
        turn
        for model, text in ((record.answer_a_model, record.answer_a_text), (record.answer_b_model, record.answer_b_text))
        for turn in (1, 2)
        if (qid, turn, model) in answers and answers[(qid, turn, model)].text == text
    }
    label_turns = labels.get((qid, record.answer_a_model, record.answer_b_model, record.human_label), set())
    constrained = candidates & label_turns
    if len(constrained) == 1:
        return next(iter(constrained)), "EXACT_TEXT_AND_HUMAN_ROW"
    if len(candidates) == 1:
        return next(iter(candidates)), "EXACT_TEXT_SOURCE_ANCHOR"
    if not candidates and len(label_turns) == 1:
        return next(iter(label_turns)), "EXACT_HUMAN_ROW_SOURCE"
    # These source records have repeated exact texts across two turns. Phase B
    # independently traced their human-row lineage to turn 2; the override is
    # keyed only by question/model source identity and is explicit in output.
    if qid in {124, 140} and (not label_turns or 2 in label_turns):
        return 2, "FORENSIC_TURN2_DISAMBIGUATION"
    raise ReconciliationError(f"unresolved source turn for frozen record {record.key}")


def build(session: Session) -> dict[str, Any]:
    questions, source, labels, raw_sha = load_raw_source()
    entries: list[dict[str, Any]] = []
    for record in frozen_records(session):
        qid = questions.get(record.prompt_text)
        if qid is None:
            raise ReconciliationError("frozen prompt absent from raw source")
        turn, origin = resolve_turn(record, qid, source, labels)
        try:
            corrected_a, corrected_b = source[(qid, turn, record.answer_a_model)], source[(qid, turn, record.answer_b_model)]
        except KeyError as exc:
            raise ReconciliationError("missing exact raw assistant answer") from exc
        changed_a, changed_b = sha(record.answer_a_text) != corrected_a.text_hash, sha(record.answer_b_text) != corrected_b.text_hash
        affected = changed_a or changed_b
        vicuna = (changed_a and record.answer_a_model == "vicuna-13b") or (changed_b and record.answer_b_model == "vicuna-13b")
        category = "SOURCE_EXACT" if not affected else "VICUNA_V13_OR_PROMPT_SHADOWING" if vicuna else "NON_VICUNA_SOURCE_SUBSTITUTION"
        entries.append({
            "frozen_record_key": record.key, "question_id": qid, "turn": turn,
            "model_1": record.answer_a_model, "model_2": record.answer_b_model,
            "frozen_answer_ids": [record.answer_a_id, record.answer_b_id],
            "frozen_answer_hashes": [sha(record.answer_a_text), sha(record.answer_b_text)],
            "corrected_source_answer_hashes": [corrected_a.text_hash, corrected_b.text_hash],
            "upstream_source_rows": [{"dataset": "lmsys/mt_bench_human_judgments", "question_id": qid, "turn": turn, "model": corrected_a.model}, {"dataset": "lmsys/mt_bench_human_judgments", "question_id": qid, "turn": turn, "model": corrected_b.model}],
            "human_reference_label": record.human_label, "status": "SOURCE_CORRECTION_REQUIRED" if affected else "SOURCE_EXACT",
            "root_cause_category": category, "source_provenance": origin, "provider_rerun_required": affected,
        })
    affected = sorted(entry["frozen_record_key"] for entry in entries if entry["status"] == "SOURCE_CORRECTION_REQUIRED")
    if len(entries) != 1568 or len(set(entry["frozen_record_key"] for entry in entries)) != 1568 or any(entry["status"] not in {"SOURCE_EXACT", "SOURCE_CORRECTION_REQUIRED"} for entry in entries):
        raise ReconciliationError("reconciliation completeness invariant failed")
    artifact = {
        "artifact_identity": IDENTITY, "generation_policy": POLICY, "raw_source_sha256": raw_sha,
        "historical_forensic_claim": {"affected": 491, "vicuna": 480, "other_substitutions": 8, "previously_unresolved": 3, "per_record_set_persisted": False},
        "reconstructed_result": {"frozen_records": len(entries), "source_exact": len(entries) - len(affected), "source_correction_required": len(affected), "unresolved": 0, "vicuna_affected": sum(entry["root_cause_category"] == "VICUNA_V13_OR_PROMPT_SHADOWING" for entry in entries), "non_vicuna_affected": sum(entry["root_cause_category"] == "NON_VICUNA_SOURCE_SUBSTITUTION" for entry in entries)},
        "prior_count_discrepancy": {"prior_affected_count": 491, "reconstructed_affected_count": len(affected), "difference": len(affected) - 491, "explanation": "The prior Phase B per-record set was never persisted. The independently reproducible raw-text criterion finds 482 Vicuna-shadowing records and 16 non-Vicuna substitutions, rather than the prior aggregate 480 and 11. Exact set intersection and differences cannot be reconstructed without the missing prior record keys; this artifact supersedes the count only, not historical evidence."},
        "affected_record_keys": affected, "records": entries,
    }
    return artifact


def artifact_sha(artifact: dict[str, Any]) -> str:
    return stable_sha(artifact)


def write(artifact: dict[str, Any], path: Path = OUTPUT) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return sha(path.read_bytes())


def main() -> int:
    from backend.core.database import SessionLocal
    with SessionLocal() as session:
        artifact = build(session)
    print(write(artifact))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
