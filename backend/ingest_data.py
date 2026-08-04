"""
ingest_data.py
==============
ETL pipeline for the LLM-as-a-Judge Reliability Lab.

Ingests MT-Bench datasets from the root data/ directory into PostgreSQL
using SQLAlchemy models defined in backend/models.py.

Steps:
  A. Ingest Prompts     → prompts table (stores full multi-turn context for Turn 2)
  B. Ingest Answers     → answers table (all model JSONL files + fallback extraction from human_judgment.jsonl)
  C. Ingest Human Pref  → human_preferences table

Idempotent: safe to run multiple times without duplicating rows.
Uses cryptographic MD5 text hashing for rock-solid answer deduplication.

Usage (from project root):
    python backend/ingest_data.py
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

import jsonlines
from sqlalchemy import select
from sqlalchemy.orm import Session
from tqdm import tqdm

# ── path setup ──────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).parent.resolve()
ROOT_DIR = BACKEND_DIR.parent.resolve()
DATA_DIR = ROOT_DIR / "data"
sys.path.insert(0, str(BACKEND_DIR))

from database import SessionLocal, engine, Base  # noqa: E402
import models  # noqa: E402

# ── logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── constants ─────────────────────────────────────────────────────────────────
def discover_model_files(data_dir: Path) -> dict[str, str]:
    """
    Dynamically scan the data/ directory for all candidate model JSONL files
    (excluding human preference/judgment datasets and question prompt files)
    and map stem -> canonical model name.
    """
    model_files: dict[str, str] = {}
    if data_dir.exists():
        for file_path in data_dir.glob("*.jsonl"):
            stem = file_path.stem
            if stem not in ("human_judgment", "human_preferences", "judgments", "question", "questions", "prompts"):
                model_files[stem] = stem
    if not model_files:
        model_files = {
            "gpt-4":          "gpt-4",
            "gpt-3.5-turbo":  "gpt-3.5-turbo",
            "claude-v1":      "claude-v1",
            "llama-13b":      "llama-13b",
            "vicuna-13b":     "vicuna-13b",
            "alpaca-13b":     "alpaca-13b",
        }
    return model_files


MODEL_FILES: dict[str, str] = discover_model_files(DATA_DIR)

MODEL_ALIASES: dict[str, str] = {
    "vicuna-13b-v1.2": "vicuna-13b",
}

BATCH_SIZE = 500


# ── helpers ──────────────────────────────────────────────────────────────────
def word_count(text: str) -> int:
    """Return the number of whitespace-delimited tokens in text."""
    return len(text.split())


def compute_text_hash(text: str) -> str:
    """Compute stable MD5 hex hash of normalized text for cryptographic deduplication."""
    return hashlib.md5(text.strip().encode("utf-8")).hexdigest()


def classify_format(text: str) -> str:
    if not text:
        return "plain_text"

    score = 0
    if re.search(r'(?m)^#{1,6}\s', text):
        score += 1
    if re.search(r'\*\*.*?\*\*', text):
        score += 1
    if re.search(r'(?m)^\s*[*\-]\s', text):
        score += 1
    if re.search(r'(?m)^\s*\d+\.\s', text):
        score += 1
    if re.search(r'```', text):
        score += 2

    return "markdown_heavy" if score >= 2 else "plain_text"


def count_lines(path: Path) -> int:
    with open(path, "rb") as f:
        return sum(1 for _ in f)


# ── Step A: Ingest Prompts ────────────────────────────────────────────────────
def ingest_prompts(db: Session) -> dict[int, int]:
    """
    Parse question.jsonl and upsert rows into the prompts table.
    Stores multi-turn prompt context (Turn 1 + Turn 2 follow-up) to ensure AI judge 
    evaluators do not evaluate Turn 2 responses in isolation.
    """
    path = DATA_DIR / "question.jsonl"
    total = count_lines(path)
    question_id_to_db_id: dict[int, int] = {}
    new_count = 0

    log.info("Step A – Ingesting prompts from %s (%d lines)", path.name, total)

    with jsonlines.open(path) as reader:
        for record in tqdm(reader, total=total, desc="Prompts", unit="row"):
            qid: int = record["question_id"]
            category: str = record.get("category", "unknown")
            turns: list[str] = record.get("turns", [])

            if not turns:
                log.warning("  question_id=%s has no turns – skipping", qid)
                continue

            # Multi-turn prompt context concatenation
            if len(turns) == 1:
                text: str = turns[0]
            else:
                text: str = turns[0] + "\n\n[Follow-up Question]: " + turns[1]

            existing = db.get(models.Prompt, qid)
            if existing:
                if existing.text != text:
                    existing.text = text
                    db.add(existing)
                question_id_to_db_id[qid] = existing.id
                continue

            prompt = models.Prompt(id=qid, text=text, category=category)
            db.add(prompt)
            question_id_to_db_id[qid] = qid
            new_count += 1

    db.commit()
    log.info("  → %d new prompts inserted (total mapped: %d)", new_count, len(question_id_to_db_id))
    return question_id_to_db_id


# ── Step B: Ingest Answers ────────────────────────────────────────────────────
def ingest_answers(
    db: Session,
    question_id_to_db_id: dict[int, int],
) -> dict[tuple[int, str, int], int]:
    """
    Parse model JSONL files + fallback extraction from human_judgment.jsonl.
    Uses MD5 text hash for cryptographic deduplication.
    """
    answer_key_to_db_id: dict[tuple[int, str, int], int] = {}

    log.info("Step B – Pre-loading existing answers with MD5 text hashes …")
    existing_answers = db.execute(
        select(
            models.Answer.id,
            models.Answer.prompt_id,
            models.Answer.model_name,
            models.Answer.text,
            models.Answer.word_count,
        )
    ).all()

    # Stable dedup key using cryptographic MD5 hash of answer text
    existing_keys: set[tuple[int, str, str]] = {
        (row.prompt_id, row.model_name, compute_text_hash(row.text))
        for row in existing_answers if row.text
    }
    log.info("  → %d answers already in DB", len(existing_answers))

    total_new = 0
    batch: list[models.Answer] = []

    # 1. Parse explicit model JSONL files
    for file_stem, model_name in MODEL_FILES.items():
        path = DATA_DIR / f"{file_stem}.jsonl"
        if not path.exists():
            log.warning("  Model file not found: %s – will fallback to human_judgment.jsonl", path)
            continue

        total_lines = count_lines(path)
        log.info("  Processing %s (%d lines, model=%s) …", path.name, total_lines, model_name)
        file_new = 0

        with jsonlines.open(path) as reader:
            for record in tqdm(reader, total=total_lines, desc=f"  {model_name}", unit="row"):
                qid: int = record.get("question_id")
                prompt_db_id = question_id_to_db_id.get(qid)
                if prompt_db_id is None:
                    continue

                choices: list[dict] = record.get("choices", [])
                if not choices:
                    continue

                turns: list[str] = choices[0].get("turns", [])

                for turn_idx, turn_text in enumerate(turns):
                    if not isinstance(turn_text, str):
                        turn_text = str(turn_text)

                    wc = word_count(turn_text)
                    thash = compute_text_hash(turn_text)
                    dedup_key = (prompt_db_id, model_name, thash)

                    if dedup_key in existing_keys:
                        continue

                    answer = models.Answer(
                        prompt_id=prompt_db_id,
                        model_name=model_name,
                        text=turn_text,
                        word_count=wc,
                        format_type=classify_format(turn_text),
                    )
                    batch.append(answer)
                    existing_keys.add(dedup_key)
                    file_new += 1
                    total_new += 1

                    if len(batch) >= BATCH_SIZE:
                        db.add_all(batch)
                        db.flush()
                        batch.clear()

        log.info("    → %d new answers inserted for %s", file_new, model_name)

    # 2. Fallback Extraction from human_judgment.jsonl for missing candidate model responses
    hj_path = DATA_DIR / "human_judgment.jsonl"
    if hj_path.exists():
        log.info("  Scanning %s for fallback candidate answer extraction …", hj_path.name)
        fallback_new = 0
        with jsonlines.open(hj_path) as reader:
            for record in reader:
                qid: int = record.get("question_id")
                prompt_db_id = question_id_to_db_id.get(qid)
                if prompt_db_id is None:
                    continue

                for conv_key, model_key in [("conversation_a", "model_a"), ("conversation_b", "model_b")]:
                    raw_mname = record.get(model_key, "")
                    mname = MODEL_ALIASES.get(raw_mname, raw_mname)
                    conv_turns = record.get(conv_key, [])
                    
                    if not mname or not conv_turns:
                        continue

                    for turn_idx, turn_obj in enumerate(conv_turns):
                        turn_text = turn_obj.get("content", "") if isinstance(turn_obj, dict) else str(turn_obj)
                        if not turn_text:
                            continue

                        wc = word_count(turn_text)
                        thash = compute_text_hash(turn_text)
                        dedup_key = (prompt_db_id, mname, thash)

                        if dedup_key in existing_keys:
                            continue

                        answer = models.Answer(
                            prompt_id=prompt_db_id,
                            model_name=mname,
                            text=turn_text,
                            word_count=wc,
                            format_type=classify_format(turn_text),
                        )
                        batch.append(answer)
                        existing_keys.add(dedup_key)
                        fallback_new += 1
                        total_new += 1

                        if len(batch) >= BATCH_SIZE:
                            db.add_all(batch)
                            db.flush()
                            batch.clear()

        if fallback_new > 0:
            log.info("    → %d fallback candidate answers extracted from human_judgment.jsonl", fallback_new)

    if batch:
        db.add_all(batch)
        db.flush()
        batch.clear()

    db.commit()

    log.info("Step B – Rebuilding answer lookup table after commit …")
    all_answers = db.execute(
        select(models.Answer.id, models.Answer.prompt_id, models.Answer.model_name, models.Answer.text)
    ).all()

    answer_key_to_db_id.clear()
    per_model_turns: dict[tuple[int, str], list[tuple[int, str]]] = {}
    for row in all_answers:
        per_model_turns.setdefault((row.prompt_id, row.model_name), []).append(
            (row.id, row.text)
        )

    for (pid, mname), id_text_pairs in per_model_turns.items():
        id_text_pairs.sort(key=lambda x: x[0])
        for turn_idx, (ans_id, _) in enumerate(id_text_pairs):
            answer_key_to_db_id[(pid, mname, turn_idx)] = ans_id

    log.info(
        "  → %d new answers inserted total; %d answer keys mapped",
        total_new,
        len(answer_key_to_db_id),
    )
    return answer_key_to_db_id


# ── Step C: Ingest Human Preferences ─────────────────────────────────────────
def ingest_human_preferences(
    db: Session,
    question_id_to_db_id: dict[int, int],
    answer_key_to_db_id: dict[tuple[int, str, int], int],
) -> None:
    """
    Parse human_judgment.jsonl and insert into human_preferences table.
    """
    path = DATA_DIR / "human_judgment.jsonl"
    total = count_lines(path)
    log.info("Step C – Ingesting human preferences from %s (%d lines)", path.name, total)

    existing_prefs: set[tuple[int, int, int]] = set(
        db.execute(
            select(
                models.HumanPreference.prompt_id,
                models.HumanPreference.answer_a_id,
                models.HumanPreference.answer_b_id,
            )
        ).all()
    )
    log.info("  → %d human preferences already in DB", len(existing_prefs))

    batch: list[models.HumanPreference] = []
    skipped = 0
    new_count = 0

    with jsonlines.open(path) as reader:
        for record in tqdm(reader, total=total, desc="HumanPrefs", unit="row"):
            qid: int = record.get("question_id")
            model_a: str = MODEL_ALIASES.get(record.get("model_a", ""), record.get("model_a", ""))
            model_b: str = MODEL_ALIASES.get(record.get("model_b", ""), record.get("model_b", ""))
            winner_label: str = record.get("winner", "")
            turn_idx: int = int(record.get("turn", 1)) - 1

            prompt_db_id = question_id_to_db_id.get(qid)
            if prompt_db_id is None:
                log.debug("    question_id=%s not found → skipping", qid)
                skipped += 1
                continue

            answer_a_id = answer_key_to_db_id.get((prompt_db_id, model_a, turn_idx))
            answer_b_id = answer_key_to_db_id.get((prompt_db_id, model_b, turn_idx))

            if answer_a_id is None or answer_b_id is None:
                log.debug(
                    "    Missing answer FK for q=%s model_a=%s model_b=%s turn=%s → skipping",
                    qid, model_a, model_b, turn_idx,
                )
                skipped += 1
                continue

            winner_id: Optional[int] = None
            if winner_label == "model_a":
                winner_id = answer_a_id
            elif winner_label == "model_b":
                winner_id = answer_b_id

            dedup = (prompt_db_id, answer_a_id, answer_b_id)
            if dedup in existing_prefs:
                continue

            pref = models.HumanPreference(
                prompt_id=prompt_db_id,
                answer_a_id=answer_a_id,
                answer_b_id=answer_b_id,
                winner_id=winner_id,
            )
            batch.append(pref)
            existing_prefs.add(dedup)
            new_count += 1

            if len(batch) >= BATCH_SIZE:
                db.add_all(batch)
                db.flush()
                batch.clear()

    if batch:
        db.add_all(batch)
        db.flush()

    db.commit()
    log.info(
        "  → %d new human preferences inserted; %d rows skipped (missing FK)",
        new_count, skipped,
    )


# ── Entrypoint ────────────────────────────────────────────────────────────────
def main() -> None:
    log.info("=" * 60)
    log.info("LLM-as-a-Judge Reliability Lab – Data Ingestion Pipeline")
    log.info("=" * 60)
    log.info("Data directory : %s", DATA_DIR)
    log.info("Database URL   : %s", os.getenv("DATABASE_URL", "(default from .env)"))

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        question_id_to_db_id = ingest_prompts(db)
        answer_key_to_db_id = ingest_answers(db, question_id_to_db_id)
        ingest_human_preferences(db, question_id_to_db_id, answer_key_to_db_id)

    log.info("=" * 60)
    log.info("Ingestion complete. ✓")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
