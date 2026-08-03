"""
ingest_data.py
==============
ETL pipeline for the LLM-as-a-Judge Reliability Lab.

Ingests MT-Bench datasets from the root data/ directory into PostgreSQL
using SQLAlchemy models defined in backend/models.py.

Steps:
  A. Ingest Prompts     → prompts table
  B. Ingest Answers     → answers table (all model JSONL files)
  C. Ingest Human Pref  → human_preferences table

Idempotent: safe to run multiple times without duplicating rows.

Usage (from project root):
    python backend/ingest_data.py
"""

import sys
import os
import logging
from pathlib import Path
from typing import Optional

import jsonlines
from tqdm import tqdm
from sqlalchemy import select
from sqlalchemy.orm import Session

# ── path setup ──────────────────────────────────────────────────────────────
# Ensure backend/ is on the import path so we can import database & models
BACKEND_DIR = Path(__file__).parent.resolve()
ROOT_DIR = BACKEND_DIR.parent.resolve()
DATA_DIR = ROOT_DIR / "data"
sys.path.insert(0, str(BACKEND_DIR))

from database import SessionLocal, engine, Base  # noqa: E402
import models  # noqa: E402  – registers all ORM classes with Base.metadata

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

# Maps dataset string variants in human_judgment.jsonl to canonical model names in DB
MODEL_ALIASES: dict[str, str] = {
    "vicuna-13b-v1.2": "vicuna-13b",
}

BATCH_SIZE = 500   # rows flushed per SQLAlchemy bulk call


# ── helpers ──────────────────────────────────────────────────────────────────

def word_count(text: str) -> int:
    """Return the number of whitespace-delimited tokens in text."""
    return len(text.split())


def classify_format(text: str) -> str:
    """
    Classify text format as 'markdown_heavy' or 'plain_text'.

    Checks for multiple markdown formatting syntax tokens (# headers, **bold**,
    - / * list items, numbered list items 1., or ``` code blocks).
    """
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
    """Fast line count without loading the full file."""
    with open(path, "rb") as f:
        return sum(1 for _ in f)


def get_or_none(db: Session, model, **filters):
    """Return the first ORM row matching filters, or None."""
    stmt = select(model).filter_by(**filters)
    return db.execute(stmt).scalars().first()


# ── Step A: Ingest Prompts ────────────────────────────────────────────────────

def ingest_prompts(db: Session) -> dict[int, int]:
    """
    Parse question.jsonl and upsert rows into the prompts table.

    Each question has multiple turns. We store the full first-turn text as
    the canonical prompt text (the MT-Bench convention).  The second turn is
    a follow-up instruction and is deliberately omitted from the Prompt table
    because the Answer table stores turn-level responses.

    Returns
    -------
    question_id_to_db_id : dict
        Mapping from MT-Bench question_id → database primary key.
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

            # Use the first-turn text as the canonical prompt
            text: str = turns[0]

            # Idempotency: look up by the MT-Bench question_id stored as id
            existing = db.get(models.Prompt, qid)
            if existing:
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
    Parse every model JSONL file and insert rows into the answers table.

    MT-Bench answers are multi-turn. We store each turn as a separate Answer
    row to preserve granularity (turn 0 = first turn, turn 1 = second turn).

    Returns
    -------
    answer_key_to_db_id : dict
        Mapping from (prompt_db_id, model_name, turn_index) → answer.id
    """
    answer_key_to_db_id: dict[tuple[int, str, int], int] = {}

    # Pre-load existing answers to avoid duplicates (idempotency)
    log.info("Step B – Pre-loading existing answers for idempotency check …")
    existing_answers = db.execute(
        select(
            models.Answer.id,
            models.Answer.prompt_id,
            models.Answer.model_name,
            models.Answer.word_count,
        )
    ).all()

    # We identify existing answers by (prompt_id, model_name, word_count) as a
    # lightweight dedup key – full text comparison would be expensive.
    existing_keys: set[tuple[int, str, int]] = {
        (row.prompt_id, row.model_name, row.word_count) for row in existing_answers
    }
    log.info("  → %d answers already in DB", len(existing_answers))

    # Build a full answer lookup from DB for foreign-key resolution in Step C
    answer_lookup: dict[tuple[int, str], list[tuple[int, int]]] = {}
    for row in existing_answers:
        key = (row.prompt_id, row.model_name)
        answer_lookup.setdefault(key, []).append((row.id, row.word_count))

    total_new = 0
    batch: list[models.Answer] = []

    for file_stem, model_name in MODEL_FILES.items():
        path = DATA_DIR / f"{file_stem}.jsonl"
        if not path.exists():
            log.warning("  Model file not found: %s – skipping", path)
            continue

        total_lines = count_lines(path)
        log.info("  Processing %s (%d lines, model=%s) …", path.name, total_lines, model_name)
        file_new = 0

        with jsonlines.open(path) as reader:
            for record in tqdm(reader, total=total_lines, desc=f"  {model_name}", unit="row"):
                qid: int = record.get("question_id")
                prompt_db_id = question_id_to_db_id.get(qid)
                if prompt_db_id is None:
                    log.debug("    question_id=%s not in prompts table – skipping", qid)
                    continue

                choices: list[dict] = record.get("choices", [])
                if not choices:
                    continue

                # Each choice contains multi-turn responses.
                turns: list[str] = choices[0].get("turns", [])

                for turn_idx, turn_text in enumerate(turns):
                    if not isinstance(turn_text, str):
                        turn_text = str(turn_text)

                    wc = word_count(turn_text)
                    dedup_key = (prompt_db_id, model_name, wc)

                    if dedup_key in existing_keys:
                        # Try to populate answer_key_to_db_id for existing rows
                        # so Step C can still resolve foreign keys.
                        for ans_id, ans_wc in answer_lookup.get(
                            (prompt_db_id, model_name), []
                        ):
                            if ans_wc == wc:
                                answer_key_to_db_id[
                                    (prompt_db_id, model_name, turn_idx)
                                ] = ans_id
                                break
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

                    # Flush batch for memory efficiency
                    if len(batch) >= BATCH_SIZE:
                        db.add_all(batch)
                        db.flush()
                        batch.clear()

        log.info("    → %d new answers inserted for %s", file_new, model_name)

    # Flush remaining batch
    if batch:
        db.add_all(batch)
        db.flush()
        batch.clear()

    db.commit()

    # Re-query the full answers table now that everything is committed, to build
    # a reliable (prompt_id, model_name) → list[(id, word_count)] lookup for Step C.
    log.info("Step B – Rebuilding answer lookup table after commit …")
    all_answers = db.execute(
        select(models.Answer.id, models.Answer.prompt_id, models.Answer.model_name, models.Answer.word_count)
    ).all()

    answer_key_to_db_id.clear()
    per_model_turns: dict[tuple[int, str], list[tuple[int, int]]] = {}
    for row in all_answers:
        per_model_turns.setdefault((row.prompt_id, row.model_name), []).append(
            (row.id, row.word_count)
        )

    # Reconstruct (prompt_id, model_name, turn_idx) → answer_id by sorting
    # answers by id ascending (insertion order = turn order).
    for (pid, mname), id_wc_pairs in per_model_turns.items():
        id_wc_pairs.sort(key=lambda x: x[0])  # sort by answer.id
        for turn_idx, (ans_id, _) in enumerate(id_wc_pairs):
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

    Each record includes:
      - question_id, model_a, model_b  → resolve to FK ids
      - winner  ("model_a" | "model_b" | "tie")
      - turn    (1-indexed; convert to 0-indexed for our keys)

    Skips rows where FK resolution fails (missing prompt or answer).
    """
    path = DATA_DIR / "human_judgment.jsonl"
    total = count_lines(path)
    log.info("Step C – Ingesting human preferences from %s (%d lines)", path.name, total)

    # Build a set of existing (prompt_id, answer_a_id, answer_b_id) tuples for dedup
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
            # human_judgment turn is 1-indexed; convert to 0-indexed
            turn_idx: int = int(record.get("turn", 1)) - 1

            # ── resolve prompt FK ─────────────────────────────────────────
            prompt_db_id = question_id_to_db_id.get(qid)
            if prompt_db_id is None:
                log.debug("    question_id=%s not found → skipping", qid)
                skipped += 1
                continue

            # ── resolve answer FKs ────────────────────────────────────────
            answer_a_id = answer_key_to_db_id.get((prompt_db_id, model_a, turn_idx))
            answer_b_id = answer_key_to_db_id.get((prompt_db_id, model_b, turn_idx))

            if answer_a_id is None or answer_b_id is None:
                log.debug(
                    "    Missing answer FK for q=%s model_a=%s model_b=%s turn=%s → skipping",
                    qid, model_a, model_b, turn_idx,
                )
                skipped += 1
                continue

            # ── resolve winner FK ─────────────────────────────────────────
            winner_id: Optional[int] = None
            if winner_label == "model_a":
                winner_id = answer_a_id
            elif winner_label == "model_b":
                winner_id = answer_b_id
            # "tie" or unknown → winner_id stays None (allowed by schema)

            # ── idempotency check ─────────────────────────────────────────
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

    # Ensure all tables exist before writing
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        # Step A
        question_id_to_db_id = ingest_prompts(db)

        # Step B
        answer_key_to_db_id = ingest_answers(db, question_id_to_db_id)

        # Step C
        ingest_human_preferences(db, question_id_to_db_id, answer_key_to_db_id)

    log.info("=" * 60)
    log.info("Ingestion complete. ✓")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
