"""
run_evaluation.py
=================
Evaluation orchestrator for the LLM-as-a-Judge Reliability Lab.

This script fetches every HumanPreference record that does not yet have a
corresponding JudgeDecision, then runs the G-EVAL judge on each pair and
persists the result.

Key design principles
---------------------
* Idempotent   — safe to kill and restart. Already-evaluated pairs are
                 skipped automatically via a NOT EXISTS sub-query.
* Position bias — for each pair, the order in which answers are shown to
                 the judge (Position A / Position B) is chosen RANDOMLY and
                 independently of the original human-preference ordering.
                 The chosen answer is recorded in JudgeDecision.position_a_id
                 so your thesis can measure LLM position bias post-hoc.
* Resilient    — API errors on a single item are logged and skipped; they
                 do NOT crash the whole run.
* Observable   — tqdm progress bar + structured logging at INFO level.
* Configurable — judge model, API key, and request delay are all controlled
                 via CLI arguments or environment variables.

Usage (from project root, with venv active)
-------------------------------------------
    # Basic run (uses default model gpt-4o)
    python backend/run_evaluation.py

    # Specify a different judge model
    python backend/run_evaluation.py --model gpt-4-turbo

    # Dry-run: print stats without calling the API
    python backend/run_evaluation.py --dry-run

    # Limit to N evaluations (useful for testing)
    python backend/run_evaluation.py --limit 10

    # Add a fixed pause between API calls (seconds) to stay under rate limits
    python backend/run_evaluation.py --delay 1.0

Environment variables (in .env or shell)
-----------------------------------------
    DATABASE_URL    PostgreSQL connection string (loaded by database.py)
    OPENAI_API_KEY  Your OpenAI secret key (required unless --dry-run)
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys
import time
from pathlib import Path
from typing import Optional

# ── path setup ────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# Load .env from the project root BEFORE importing database.py
from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

from sqlalchemy import select, not_, exists, func
from sqlalchemy.orm import Session
from tqdm import tqdm

from database import SessionLocal, engine, Base  # noqa: E402
import models                                    # noqa: E402
from judge_engine import call_judge, JudgeResult, Verdict  # noqa: E402

# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── CLI arguments ─────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the LLM-as-a-Judge evaluation engine.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--model",
        default="gpt-4o",
        help="OpenAI model to use as the judge.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Seconds to wait between API calls (avoids rate-limit errors).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of preferences to evaluate (for testing).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch pending items and print stats, but do NOT call the API.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible position-A/B assignment.",
    )
    return parser.parse_args()


# ── Database helpers ──────────────────────────────────────────────────────────

def fetch_pending_preferences(
    db: Session,
    judge_model_name: str,
    limit: Optional[int] = None,
) -> list[models.HumanPreference]:
    """
    Return HumanPreference rows that have no JudgeDecision yet for the given
    judge model.

    Uses a NOT EXISTS sub-query so the check is done inside the database,
    which scales to millions of rows without loading them into Python memory.
    """
    already_judged_subq = (
        select(models.JudgeDecision.id)
        .where(
            models.JudgeDecision.prompt_id       == models.HumanPreference.prompt_id,
            models.JudgeDecision.answer_a_id     == models.HumanPreference.answer_a_id,
            models.JudgeDecision.answer_b_id     == models.HumanPreference.answer_b_id,
            models.JudgeDecision.judge_model_name == judge_model_name,
        )
        .correlate(models.HumanPreference)
        .exists()
    )

    stmt = (
        select(models.HumanPreference)
        .where(not_(already_judged_subq))
        .order_by(models.HumanPreference.id)
    )

    if limit is not None:
        stmt = stmt.limit(limit)

    return list(db.execute(stmt).scalars().all())


def resolve_winner_id(
    verdict: Verdict,
    answer_pos_a_id: int,
    answer_pos_b_id: int,
) -> Optional[int]:
    """
    Map the judge's text verdict to a database answer ID.

    The verdict refers to the *position* (A or B) shown to the judge, which
    may differ from the original HumanPreference answer_a / answer_b ordering.

    Parameters
    ----------
    verdict         : "A", "B", "TIE", or "UNKNOWN"
    answer_pos_a_id : DB id of the answer shown in Position A to the judge.
    answer_pos_b_id : DB id of the answer shown in Position B to the judge.

    Returns
    -------
    The database id of the winning answer, or None for TIE / UNKNOWN.
    """
    if verdict == "A":
        return answer_pos_a_id
    if verdict == "B":
        return answer_pos_b_id
    return None   # TIE or UNKNOWN → NULL in DB (allowed by schema)


def save_judge_decision(
    db: Session,
    pref: models.HumanPreference,
    result: JudgeResult,
    answer_pos_a_id: int,
    answer_pos_b_id: int,
) -> models.JudgeDecision:
    """
    Persist one JudgeDecision row and return the ORM object.

    Note on answer_a_id / answer_b_id in JudgeDecision
    ---------------------------------------------------
    We preserve the ORIGINAL HumanPreference ordering for answer_a_id and
    answer_b_id so the tables remain join-compatible.  The POSITION shown to
    the judge is captured separately in position_a_id.  This lets your thesis
    compute position-bias metrics by comparing the two columns post-hoc.
    """
    winner_id = resolve_winner_id(result.verdict, answer_pos_a_id, answer_pos_b_id)

    decision = models.JudgeDecision(
        prompt_id        = pref.prompt_id,
        judge_model_name = result.model_name,
        answer_a_id      = pref.answer_a_id,    # original HumanPreference ordering
        answer_b_id      = pref.answer_b_id,    # original HumanPreference ordering
        position_a_id    = answer_pos_a_id,     # which answer the judge saw in slot A
        winner_id        = winner_id,
        reasoning        = result.reasoning,
    )
    db.add(decision)
    db.commit()
    return decision


# ── Main orchestrator ─────────────────────────────────────────────────────────

def run_evaluation(args: argparse.Namespace) -> None:
    log.info("=" * 64)
    log.info("LLM-as-a-Judge Reliability Lab — Evaluation Engine")
    log.info("=" * 64)
    log.info("Judge model  : %s", args.model)
    log.info("API delay    : %.1f s between calls", args.delay)
    log.info("Limit        : %s", args.limit or "all pending")
    log.info("Dry run      : %s", args.dry_run)
    log.info("Random seed  : %d", args.seed)

    random.seed(args.seed)

    # ── Evaluation Client Setup ───────────────────────────────────────────────
    log.info("Evaluation engine ready. Client will be resolved dynamically per model family.")

    # ── Fetch pending items ───────────────────────────────────────────────────
    with SessionLocal() as db:
        log.info("Fetching pending human_preferences …")
        pending = fetch_pending_preferences(db, args.model, args.limit)

    total_pending = len(pending)
    log.info("%d preference(s) pending evaluation.", total_pending)

    if total_pending == 0:
        log.info("Nothing to do — all preferences have been evaluated. Exiting.")
        return

    if args.dry_run:
        log.info("Dry-run mode: no API calls will be made.")
        log.info("Sample of first 5 pending IDs: %s",
                 [p.id for p in pending[:5]])
        log.info("Dry-run complete.")
        return

    # ── Counters ──────────────────────────────────────────────────────────────
    n_success = 0
    n_skip    = 0   # UNKNOWN verdict (parse failed but stored)
    n_error   = 0   # API / DB errors — item skipped entirely

    # ── Main evaluation loop ──────────────────────────────────────────────────
    with SessionLocal() as db:
        pbar = tqdm(
            pending,
            total=total_pending,
            desc="Evaluating",
            unit="pair",
            dynamic_ncols=True,
        )

        for pref in pbar:
            # ── Load related ORM objects ──────────────────────────────────────
            prompt  = db.get(models.Prompt, pref.prompt_id)
            ans_a   = db.get(models.Answer, pref.answer_a_id)
            ans_b   = db.get(models.Answer, pref.answer_b_id)

            if not prompt or not ans_a or not ans_b:
                log.warning(
                    "  pref.id=%d: missing related object (prompt=%s, ans_a=%s, ans_b=%s) — skipping.",
                    pref.id, bool(prompt), bool(ans_a), bool(ans_b),
                )
                n_error += 1
                continue

            # ── Randomise position A / B for position-bias research ───────────
            # Independently of the HumanPreference order, decide which answer
            # the judge will see in the "A" slot.  This is the core mechanism
            # that lets us measure LLM position bias post-hoc.
            if random.random() < 0.5:
                judge_pos_a, judge_pos_b = ans_a, ans_b
            else:
                judge_pos_a, judge_pos_b = ans_b, ans_a

            # ── Call the judge ────────────────────────────────────────────────
            try:
                result: JudgeResult = call_judge(
                    question=prompt.text,
                    answer_a=judge_pos_a.text,
                    answer_b=judge_pos_b.text,
                    model_name=args.model,
                    temperature=0.0,
                )

                # ── Persist result ────────────────────────────────────────────
                save_judge_decision(
                    db=db,
                    pref=pref,
                    result=result,
                    answer_pos_a_id=judge_pos_a.id,
                    answer_pos_b_id=judge_pos_b.id,
                )

                if result.verdict == "UNKNOWN":
                    n_skip += 1
                    log.warning(
                        "  pref.id=%d: verdict could not be parsed — stored as NULL winner.",
                        pref.id,
                    )
                else:
                    n_success += 1

                pbar.set_postfix(
                    ok=n_success,
                    unknown=n_skip,
                    err=n_error,
                    tokens=result.input_tokens + result.output_tokens,
                )

            except Exception as exc:
                n_error += 1
                log.error(
                    "  pref.id=%d: API/DB error — %s. Skipping this item.",
                    pref.id, exc,
                )
                pbar.set_postfix(ok=n_success, unknown=n_skip, err=n_error)

            # ── Rate-limit delay ──────────────────────────────────────────────
            if args.delay > 0:
                time.sleep(args.delay)

    # ── Final summary ─────────────────────────────────────────────────────────
    log.info("=" * 64)
    log.info("Evaluation complete.")
    log.info("  ✅  Successful decisions : %d", n_success)
    log.info("  ⚠️   Unknown verdicts     : %d  (stored, winner=NULL)", n_skip)
    log.info("  ❌  Errors / skipped     : %d  (not stored)", n_error)
    log.info("  Total processed          : %d / %d", n_success + n_skip, total_pending)
    log.info("=" * 64)


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = parse_args()
    run_evaluation(args)
