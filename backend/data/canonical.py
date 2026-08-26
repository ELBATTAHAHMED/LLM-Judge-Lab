"""Canonical, source-text-keyed controlled-study data.

This module is intentionally independent of the historical working database.
It validates the committed raw LMSYS snapshot by identity and SHA-256, then
builds a fresh database from the committed canonical record manifest.  It never
selects an answer by database ID or insertion order.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.controlled_models import DatasetVersion
from backend.core.models import Answer, HumanPreference, Prompt


ROOT = Path(__file__).resolve().parents[2]
RAW_HUMAN_PATH = ROOT / "data" / "human_judgment.jsonl"
RAW_QUESTION_PATH = ROOT / "data" / "question.jsonl"
CANONICAL_PATH = ROOT / "data" / "canonical" / "source_corrected_study_v1.json"
FROZEN_RECONCILIATION_PATH = ROOT / "evidence" / "final" / "controlled_source_text_corrected_v1" / "source" / "source_text_reconciliation_v1.json"
CANONICAL_IDENTITY = "source-corrected-controlled-study-v1"
SOURCE_NAME = "lmsys-mt-bench-human-judgments-source-corrected"


class CanonicalSourceError(RuntimeError):
    """A fail-closed canonical-source validation error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def sha256(value: str | bytes) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def stable_sha(value: Any) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def canonical_model(value: str) -> str:
    return {"vicuna-13b-v1.2": "vicuna-13b"}.get(value, value)


def _label(winner: str) -> str:
    try:
        return {"model_a": "ANSWER_A", "model_b": "ANSWER_B", "tie": "TIE"}[winner]
    except KeyError as exc:
        raise CanonicalSourceError("SOURCE_RECORD_MISSING", f"unknown upstream winner {winner!r}") from exc


def _prompt(messages: list[dict[str, Any]], turn: int) -> str:
    if len(messages) < 2 * turn:
        raise CanonicalSourceError("SOURCE_RECORD_MISSING", "raw conversation lacks requested turn")
    if turn == 1:
        return str(messages[0]["content"])
    return str(messages[0]["content"]) + "\n\n[Follow-up Question]: " + str(messages[2]["content"])


@dataclass(frozen=True)
class RawAnswer:
    question_id: int
    turn: int
    model: str
    text: str

    @property
    def text_hash(self) -> str:
        return sha256(self.text)


@dataclass(frozen=True)
class RawSourceIndex:
    raw_sha256: str
    answers: dict[tuple[int, int, str], RawAnswer]
    prompts: dict[tuple[int, int], str]
    labels: dict[tuple[int, int, str, str, str], int]
    categories: dict[int, str]


def load_raw_source(
    *,
    human_path: Path = RAW_HUMAN_PATH,
    question_path: Path = RAW_QUESTION_PATH,
) -> RawSourceIndex:
    """Index raw source records and reject any ambiguous source identity."""
    raw_bytes = human_path.read_bytes()
    answers: dict[tuple[int, int, str], RawAnswer] = {}
    prompts: dict[tuple[int, int], str] = {}
    labels: dict[tuple[int, int, str, str, str], int] = defaultdict(int)
    for line in raw_bytes.splitlines():
        row = json.loads(line)
        qid, turn = int(row["question_id"]), int(row["turn"])
        model_a, model_b = canonical_model(str(row["model_a"])), canonical_model(str(row["model_b"]))
        labels[(qid, turn, model_a, model_b, _label(str(row["winner"])))] += 1
        for side in ("a", "b"):
            model = canonical_model(str(row[f"model_{side}"]))
            messages = row[f"conversation_{side}"]
            answer = RawAnswer(qid, turn, model, str(messages[2 * turn - 1]["content"]))
            key = (qid, turn, model)
            prior = answers.setdefault(key, answer)
            if prior.text != answer.text:
                raise CanonicalSourceError("AMBIGUOUS_SOURCE_IDENTITY", f"multiple texts for {key!r}")
            prompt = _prompt(messages, turn)
            prompt_key = (qid, turn)
            prior_prompt = prompts.setdefault(prompt_key, prompt)
            if prior_prompt != prompt:
                raise CanonicalSourceError("AMBIGUOUS_SOURCE_IDENTITY", f"multiple prompts for {prompt_key!r}")
    categories: dict[int, str] = {}
    for line in question_path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        categories[int(row["question_id"])] = str(row["category"])
    if not answers or not prompts or not categories:
        raise CanonicalSourceError("SOURCE_RECORD_MISSING", "raw source index is incomplete")
    return RawSourceIndex(sha256(raw_bytes), answers, prompts, dict(labels), categories)


def _body_without_hash(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "canonical_dataset_sha256"}


def load_canonical_study(path: Path = CANONICAL_PATH) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CanonicalSourceError("SOURCE_RECORD_MISSING", f"canonical manifest absent: {path}") from exc
    if payload.get("identity") != CANONICAL_IDENTITY:
        raise CanonicalSourceError("SOURCE_RECORD_MISSING", "unexpected canonical dataset identity")
    records = payload.get("records")
    if not isinstance(records, list) or len(records) != 1568:
        raise CanonicalSourceError("SOURCE_RECORD_MISSING", "canonical record count must be 1568")
    if payload.get("canonical_dataset_sha256") != stable_sha(_body_without_hash(payload)):
        raise CanonicalSourceError("SOURCE_TEXT_HASH_MISMATCH", "canonical manifest checksum mismatch")
    identities = [row.get("canonical_logical_identity") for row in records]
    if len(identities) != len(set(identities)) or any(not isinstance(value, str) for value in identities):
        raise CanonicalSourceError("AMBIGUOUS_SOURCE_IDENTITY", "canonical logical identities are not unique")
    return payload


def validate_canonical_source(
    payload: dict[str, Any] | None = None,
    *,
    human_path: Path = RAW_HUMAN_PATH,
    question_path: Path = RAW_QUESTION_PATH,
) -> tuple[dict[str, Any], RawSourceIndex]:
    """Validate all canonical records against raw source identity and hashes."""
    payload = payload or load_canonical_study()
    source = load_raw_source(human_path=human_path, question_path=question_path)
    raw = payload.get("raw_source", {})
    if raw.get("sha256") != source.raw_sha256:
        raise CanonicalSourceError("SOURCE_TEXT_HASH_MISMATCH", "raw human-source snapshot checksum mismatch")
    records = payload["records"]
    statuses: dict[str, int] = defaultdict(int)
    for record in records:
        qid, turn = int(record["question_id"]), int(record["turn"])
        prompt = source.prompts.get((qid, turn))
        if prompt is None or sha256(prompt) != record.get("prompt_sha256"):
            raise CanonicalSourceError("SOURCE_TEXT_HASH_MISMATCH", f"prompt mismatch for {(qid, turn)!r}")
        if source.categories.get(qid) != record.get("category"):
            raise CanonicalSourceError("SOURCE_RECORD_MISSING", f"missing category for question {qid}")
        source_models = []
        for answer in record.get("answers", []):
            model = str(answer.get("model"))
            expected_hash = str(answer.get("text_sha256"))
            source_answer = source.answers.get((qid, turn, model))
            if source_answer is None:
                raise CanonicalSourceError("SOURCE_RECORD_MISSING", f"answer missing for {(qid, turn, model)!r}")
            if source_answer.text_hash != expected_hash:
                raise CanonicalSourceError("SOURCE_TEXT_HASH_MISMATCH", f"answer mismatch for {(qid, turn, model)!r}")
            source_models.append(model)
        if len(source_models) != 2 or len(set(source_models)) != 2:
            raise CanonicalSourceError("AMBIGUOUS_SOURCE_IDENTITY", f"invalid pair identity for {record.get('canonical_logical_identity')}")
        expected_label = record.get("human_preference_reference_label")
        direct = source.labels.get((qid, turn, source_models[0], source_models[1], expected_label), 0)
        reversed_label = {
            "ANSWER_A": "ANSWER_B", "ANSWER_B": "ANSWER_A", "TIE": "TIE",
        }.get(expected_label)
        reversed_row = source.labels.get((qid, turn, source_models[1], source_models[0], reversed_label), 0) if reversed_label else 0
        # The two frozen reconciliation rows with repeated exact source text
        # use an explicit forensic turn-2 disambiguation.  Their human label is
        # committed in the canonical manifest; it is not inferred from a
        # different source row during a fresh build.
        forensic = record.get("source_provenance") == "FORENSIC_TURN2_DISAMBIGUATION"
        if not direct and not reversed_row and not forensic:
            raise CanonicalSourceError("SOURCE_RECORD_MISSING", f"human reference row missing for {record.get('canonical_logical_identity')}")
        statuses[str(record["reconciliation_status"])] += 1
    if statuses != {"SOURCE_EXACT": 1070, "SOURCE_CORRECTION_REQUIRED": 498}:
        raise CanonicalSourceError("SOURCE_RECORD_MISSING", f"unexpected reconciliation counts: {dict(statuses)!r}")
    return payload, source


def compare_canonical_to_frozen_reconciliation(payload: dict[str, Any] | None = None) -> dict[str, int]:
    """Check all canonical identities, labels, and hashes against frozen evidence."""
    payload = payload or load_canonical_study()
    frozen = json.loads(FROZEN_RECONCILIATION_PATH.read_text(encoding="utf-8"))
    expected = {
        row["frozen_record_key"]: (
            tuple(row["corrected_source_answer_hashes"]),
            row["human_reference_label"],
        )
        for row in frozen["records"]
    }
    actual = {
        row["frozen_reconciliation_identity"]: (
            tuple(answer["text_sha256"] for answer in row["answers"]),
            row["human_preference_reference_label"],
        )
        for row in payload["records"]
    }
    if actual != expected:
        raise CanonicalSourceError("SOURCE_TEXT_HASH_MISMATCH", "canonical data differs from frozen source reconciliation")
    return {"canonical_logical_identities": len(actual), "source_hash_matches": len(actual), "source_hash_mismatches": 0}


def build_fresh_dataset(session: Session, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Populate an empty database using only canonical data and raw source text."""
    payload, source = validate_canonical_source(payload)
    existing = session.scalar(select(Prompt.id).limit(1))
    if existing is not None:
        raise CanonicalSourceError("AMBIGUOUS_SOURCE_IDENTITY", "fresh build requires an empty prompts table")
    records = sorted(payload["records"], key=lambda row: (int(row["question_id"]), int(row["turn"]), row["canonical_logical_identity"]))
    prompt_keys = sorted({(int(row["question_id"]), int(row["turn"])) for row in records})
    question_ids = sorted({question_id for question_id, _ in prompt_keys})
    turn_1_prompt_records = sum(turn == 1 for _, turn in prompt_keys)
    turn_2_prompt_records = sum(turn == 2 for _, turn in prompt_keys)
    dataset = DatasetVersion(
        source_name=SOURCE_NAME,
        version=CANONICAL_IDENTITY,
        license_text="CC BY 4.0",
        source_uri="https://huggingface.co/datasets/lmsys/mt_bench_human_judgments",
        source_checksum=payload["canonical_dataset_sha256"],
        checksum_algorithm="SHA-256",
        import_status="SUCCEEDED",
        imported_prompt_count=len(prompt_keys),
        imported_annotation_count=len(records),
        notes="Built from canonical source-text identities; no historical database ordering was used.",
    )
    session.add(dataset)
    prompt_ids: dict[tuple[int, int], int] = {}
    answer_ids: dict[tuple[int, int, str], int] = {}
    for qid, turn in prompt_keys:
        prompt = Prompt(text=source.prompts[(qid, turn)], category=source.categories[qid])
        session.add(prompt); session.flush()
        prompt_ids[(qid, turn)] = prompt.id
    answer_keys = sorted({(int(row["question_id"]), int(row["turn"]), str(answer["model"])) for row in records for answer in row["answers"]})
    for qid, turn, model in answer_keys:
        raw_answer = source.answers[(qid, turn, model)]
        answer = Answer(prompt_id=prompt_ids[(qid, turn)], model_name=model, text=raw_answer.text, word_count=len(raw_answer.text.split()), format_type="plain_text")
        session.add(answer); session.flush()
        answer_ids[(qid, turn, model)] = answer.id
    for record in records:
        qid, turn = int(record["question_id"]), int(record["turn"])
        a, b = record["answers"]
        a_id, b_id = answer_ids[(qid, turn, a["model"])], answer_ids[(qid, turn, b["model"])]
        label = record["human_preference_reference_label"]
        winner_id = None if label == "TIE" else a_id if label == "ANSWER_A" else b_id if label == "ANSWER_B" else None
        if label not in {"ANSWER_A", "ANSWER_B", "TIE"}:
            raise CanonicalSourceError("SOURCE_RECORD_MISSING", f"invalid label for {record['canonical_logical_identity']}")
        session.add(HumanPreference(prompt_id=prompt_ids[(qid, turn)], answer_a_id=a_id, answer_b_id=b_id, winner_id=winner_id))
    dataset.imported_answer_count = len(answer_ids)
    session.flush()
    return {
        "dataset_version_id": str(dataset.id),
        "identity": payload["identity"],
        "canonical_dataset_sha256": payload["canonical_dataset_sha256"],
        "controlled_records": len(records),
        "source_exact": 1070,
        "source_correction_required": 498,
        "unresolved": 0,
        "distinct_mt_bench_questions": len(question_ids),
        "question_id_min": question_ids[0],
        "question_id_max": question_ids[-1],
        "turn_1_prompt_records": turn_1_prompt_records,
        "turn_2_prompt_records": turn_2_prompt_records,
        "turn_level_prompt_records": len(prompt_ids),
        "answers": len(answer_ids),
    }


def verify_fresh_dataset(session: Session, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compare a fresh build against the same canonical identities and hashes."""
    payload, source = validate_canonical_source(payload)
    from sqlalchemy.orm import aliased

    answer_a, answer_b = aliased(Answer), aliased(Answer)
    rows = session.execute(
        select(HumanPreference, Prompt, answer_a, answer_b)
        .join(Prompt, Prompt.id == HumanPreference.prompt_id)
        .join(answer_a, answer_a.id == HumanPreference.answer_a_id)
        .join(answer_b, answer_b.id == HumanPreference.answer_b_id)
    ).all()
    actual: list[tuple[int, str, str, str, str]] = []
    for pref, prompt, answer_a, answer_b in rows:
        candidates = [(key, text) for key, text in source.prompts.items() if text == prompt.text]
        if len(candidates) != 1:
            raise CanonicalSourceError("AMBIGUOUS_SOURCE_IDENTITY", "fresh prompt cannot be resolved by source text")
        qid, turn = candidates[0][0]
        label = "TIE" if pref.winner_id is None else "ANSWER_A" if pref.winner_id == answer_a.id else "ANSWER_B" if pref.winner_id == answer_b.id else "INVALID"
        actual.append((qid, str(turn), answer_a.model_name, sha256(answer_a.text), answer_b.model_name + "|" + sha256(answer_b.text) + "|" + label))
    expected = [
        (int(row["question_id"]), str(row["turn"]), row["answers"][0]["model"], row["answers"][0]["text_sha256"], row["answers"][1]["model"] + "|" + row["answers"][1]["text_sha256"] + "|" + row["human_preference_reference_label"])
        for row in payload["records"]
    ]
    if sorted(actual) != sorted(expected):
        raise CanonicalSourceError("SOURCE_TEXT_HASH_MISMATCH", f"fresh dataset identity mismatch: expected {len(expected)}, actual {len(actual)}")
    return {"source_hash_matches": len(expected), "source_hash_mismatches": 0, "controlled_records": len(actual), "unresolved": 0}
