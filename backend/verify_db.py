"""
verify_db.py
============
QA Health-Check script for the LLM-as-a-Judge Reliability Lab database.

Runs 4 categories of checks against the PostgreSQL database:
  1. Row Counts           – total rows per table
  2. Data Integrity       – orphaned FKs, NULL FK columns
  3. Feature Check        – word_count validity in answers
  4. Distribution Check   – answer count grouped by model_name

Usage (from project root, with venv active):
    python backend/verify_db.py
"""

import sys
import os
import io
from pathlib import Path

# Ensure stdout handles UTF-8 on Windows console without UnicodeEncodeError
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── path setup ────────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from database import SessionLocal, engine, Base  # noqa: E402
import models  # noqa: E402

# ── helpers ───────────────────────────────────────────────────────────────────

PASS = "\033[92m  [PASS]\033[0m"
FAIL = "\033[91m  [FAIL]\033[0m"
INFO = "\033[94m  [INFO]\033[0m"
WARN = "\033[93m  [WARN]\033[0m"
SEP  = "-" * 60

all_passed = True


def ok(label: str, detail: str = "") -> None:
    suffix = f"  →  {detail}" if detail else ""
    print(f"{PASS}  {label}{suffix}")


def fail(label: str, detail: str = "") -> None:
    global all_passed
    all_passed = False
    suffix = f"  →  {detail}" if detail else ""
    print(f"{FAIL}  {label}{suffix}")


def info(label: str, detail: str = "") -> None:
    suffix = f"  {detail}" if detail else ""
    print(f"{INFO}  {label}{suffix}")


def warn(label: str, detail: str = "") -> None:
    suffix = f"  →  {detail}" if detail else ""
    print(f"{WARN}  {label}{suffix}")


def section(title: str) -> None:
    print(f"\n{SEP}\n  {title}\n{SEP}")


# ── Check 1: Row Counts ───────────────────────────────────────────────────────

def check_row_counts(db: Session) -> dict[str, int]:
    section("CHECK 1 · Row Counts")

    counts: dict[str, int] = {}
    table_models = {
        "prompts":           models.Prompt,
        "answers":           models.Answer,
        "human_preferences": models.HumanPreference,
        "judge_decisions":   models.JudgeDecision,
    }

    for table_name, model in table_models.items():
        n = db.execute(select(func.count()).select_from(model)).scalar_one()
        counts[table_name] = n
        info(f"{table_name:<22}", f"{n:,} rows")

    # Sanity expectations
    if counts["prompts"] >= 80:
        ok("prompts count", f"{counts['prompts']:,} prompt rows present (benchmark + live)")
    else:
        fail("prompts count", f"expected >= 80, got {counts['prompts']}")

    if counts["answers"] > 0:
        ok("answers count", f"{counts['answers']:,} answer rows present")
    else:
        fail("answers count", "table is empty — did ingestion run?")

    if counts["human_preferences"] > 0:
        ok("human_preferences count", f"{counts['human_preferences']:,} preference rows present")
    else:
        fail("human_preferences count", "table is empty — did ingestion run?")

    return counts


# ── Check 2: Data Integrity ───────────────────────────────────────────────────

def check_data_integrity(db: Session) -> None:
    section("CHECK 2 · Data Integrity (Foreign Keys & NULLs)")

    # 2a – NULL FK columns in human_preferences (prompt_id, answer_a_id, answer_b_id are NOT NULL by schema)
    #      but let's verify at the data level too
    for col_name, col_attr in [
        ("prompt_id",   models.HumanPreference.prompt_id),
        ("answer_a_id", models.HumanPreference.answer_a_id),
        ("answer_b_id", models.HumanPreference.answer_b_id),
    ]:
        null_count = db.execute(
            select(func.count())
            .select_from(models.HumanPreference)
            .where(col_attr.is_(None))
        ).scalar_one()

        if null_count == 0:
            ok(f"human_preferences.{col_name}", "no NULLs found")
        else:
            fail(f"human_preferences.{col_name}", f"{null_count} NULL values found!")

    # 2b – Orphaned answers: answers whose prompt_id doesn't exist in prompts
    orphaned_answers = db.execute(
        select(func.count())
        .select_from(models.Answer)
        .outerjoin(models.Prompt, models.Answer.prompt_id == models.Prompt.id)
        .where(models.Prompt.id.is_(None))
    ).scalar_one()

    if orphaned_answers == 0:
        ok("Orphaned answers", "all answers have a valid prompt_id")
    else:
        fail("Orphaned answers", f"{orphaned_answers} answers point to a non-existent prompt!")

    # 2c – Orphaned human_preferences: rows whose prompt_id doesn't exist in prompts
    orphaned_prefs = db.execute(
        select(func.count())
        .select_from(models.HumanPreference)
        .outerjoin(models.Prompt, models.HumanPreference.prompt_id == models.Prompt.id)
        .where(models.Prompt.id.is_(None))
    ).scalar_one()

    if orphaned_prefs == 0:
        ok("Orphaned human_preferences (prompt)", "all preferences have a valid prompt_id")
    else:
        fail("Orphaned human_preferences (prompt)", f"{orphaned_prefs} orphaned rows!")

    # 2d – human_preferences where answer_a_id OR answer_b_id point to a missing answer
    hp = models.HumanPreference
    ans = models.Answer

    bad_a = db.execute(
        text("""
            SELECT COUNT(*) FROM human_preferences hp
            LEFT JOIN answers a ON hp.answer_a_id = a.id
            WHERE a.id IS NULL
        """)
    ).scalar_one()

    bad_b = db.execute(
        text("""
            SELECT COUNT(*) FROM human_preferences hp
            LEFT JOIN answers a ON hp.answer_b_id = a.id
            WHERE a.id IS NULL
        """)
    ).scalar_one()

    if bad_a == 0:
        ok("human_preferences.answer_a_id", "all answer_a FKs resolve correctly")
    else:
        fail("human_preferences.answer_a_id", f"{bad_a} rows point to a missing answer!")

    if bad_b == 0:
        ok("human_preferences.answer_b_id", "all answer_b FKs resolve correctly")
    else:
        fail("human_preferences.answer_b_id", f"{bad_b} rows point to a missing answer!")

    # 2e – winner_id can be NULL (ties), but non-NULL winners must point to a real answer
    bad_winner = db.execute(
        text("""
            SELECT COUNT(*) FROM human_preferences hp
            LEFT JOIN answers a ON hp.winner_id = a.id
            WHERE hp.winner_id IS NOT NULL AND a.id IS NULL
        """)
    ).scalar_one()

    if bad_winner == 0:
        ok("human_preferences.winner_id", "all non-NULL winner FKs resolve correctly")
    else:
        fail("human_preferences.winner_id", f"{bad_winner} rows have invalid winner_id!")

    # 2f – Count of ties (NULL winner_id) for transparency
    ties = db.execute(
        select(func.count())
        .select_from(models.HumanPreference)
        .where(models.HumanPreference.winner_id.is_(None))
    ).scalar_one()
    info("Tie/no-winner rows", f"{ties:,} rows where winner_id IS NULL (expected for ties)")


# ── Check 3: Feature Check (word_count) ──────────────────────────────────────

def check_word_count(db: Session) -> None:
    section("CHECK 3 · Feature Check (word_count column)")

    # 3a – Any NULL word_count?
    null_wc = db.execute(
        select(func.count())
        .select_from(models.Answer)
        .where(models.Answer.word_count.is_(None))
    ).scalar_one()

    if null_wc == 0:
        ok("NULL word_count", "no NULL values in word_count column")
    else:
        fail("NULL word_count", f"{null_wc} answers have NULL word_count!")

    # 3b – Any zero word_count (empty answers)?
    zero_wc = db.execute(
        select(func.count())
        .select_from(models.Answer)
        .where(models.Answer.word_count == 0)
    ).scalar_one()

    if zero_wc == 0:
        ok("Zero word_count", "no zero-word answers found")
    else:
        warn("Zero word_count", f"{zero_wc} answers have word_count=0 (possibly empty text)")

    # 3c – Aggregate stats
    stats = db.execute(
        select(
            func.min(models.Answer.word_count).label("min"),
            func.max(models.Answer.word_count).label("max"),
            func.round(func.avg(models.Answer.word_count), 1).label("avg"),
        )
    ).one()

    info("word_count stats",
         f"min={stats.min}  |  max={stats.max}  |  avg={stats.avg}")


# ── Check 4: Distribution by model_name ──────────────────────────────────────

def check_distribution(db: Session) -> None:
    section("CHECK 4 · Answer Distribution by Model")

    rows = db.execute(
        select(
            models.Answer.model_name,
            func.count().label("answer_count"),
            func.round(func.avg(models.Answer.word_count), 1).label("avg_words"),
        )
        .group_by(models.Answer.model_name)
        .order_by(func.count().desc())
    ).all()

    if not rows:
        fail("Distribution", "no rows found — answers table is empty!")
        return

    # Print table header
    print(f"\n  {'Model':<22} {'Answers':>8}  {'Avg Words':>10}")
    print(f"  {'-'*22}  {'-'*8}  {'-'*10}")

    counts = [r.answer_count for r in rows]

    for r in rows:
        print(f"  {r.model_name:<22} {r.answer_count:>8,}  {r.avg_words:>10}")

    print()

    # All models should have a similar count (within ±10% of the mean)
    mean = sum(counts) / len(counts)
    threshold = mean * 0.10  # 10% tolerance
    uneven = [r for r in rows if abs(r.answer_count - mean) > threshold]

    if not uneven:
        ok("Distribution evenness", f"all models within 10% of mean ({mean:.0f} answers)")
    else:
        warn(
            "Distribution evenness",
            f"these models deviate >10% from mean ({mean:.0f}): "
            + ", ".join(f"{r.model_name}={r.answer_count}" for r in uneven),
        )

    expected_models = {
        "gpt-4", "gpt-3.5-turbo", "claude-v1",
        "llama-13b", "vicuna-13b", "alpaca-13b",
    }
    found_models = {r.model_name for r in rows}
    missing = expected_models - found_models

    if not missing:
        ok("All 6 models present", str(sorted(found_models)))
    else:
        fail("Missing models", f"{missing} were not found in the answers table!")


# ── Entrypoint ────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"\n{'='*60}")
    print("  LLM-as-a-Judge Reliability Lab -- DB Verification")
    print(f"{'='*60}")

    with SessionLocal() as db:
        check_row_counts(db)
        check_data_integrity(db)
        check_word_count(db)
        check_distribution(db)

    print(f"\n{SEP}")
    if all_passed:
        print("\033[92m  [OK]  ALL CHECKS PASSED -- database looks healthy!\033[0m")
    else:
        print("\033[91m  [FAIL]  SOME CHECKS FAILED -- review the [FAIL] lines above.\033[0m")
    print(f"{SEP}\n")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
