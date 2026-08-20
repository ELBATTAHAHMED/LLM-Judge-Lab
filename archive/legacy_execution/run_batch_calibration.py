"""
run_batch_calibration.py
========================
Batch Calibration Orchestrator for the LLM-as-a-Judge Reliability Lab.

This script fetches HumanPreference benchmark records and executes the Dual A/B Swap
mitigation protocol (or other calibration strategies) across candidate answer pairs.
The resulting debiased evaluation decisions are persisted back to the PostgreSQL database
in the `judge_decisions` table under the judge_model_name '{model}_calibrated'.

Key Features:
- Idempotent: Skips already-calibrated pairs via NOT EXISTS check unless --force is used.
- Dual A/B Swap: Evaluates both original (A vs B) and inverted (B vs A) presentation orders.
  If position bias causes verdict flip, output is resolved to TIE (null winner).
- Auditable: Detailed reasoning narrative and pass-by-pass verdicts saved to DB.
- Resilient & Observable: Handles API rate limits, backoff retries, and tqdm progress display.

Usage:
    # Run batch calibration on default model (gpt-4o-mini)
    python backend/run_batch_calibration.py

    # Limit to N items for testing
    python backend/run_batch_calibration.py --limit 10

    # Specify different model or strategy
    python backend/run_batch_calibration.py --model deepseek/deepseek-chat --strategy dual_ab

    # Dry-run mode
    python backend/run_batch_calibration.py --dry-run
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

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

from sqlalchemy import select, not_, exists
from sqlalchemy.orm import Session
from tqdm import tqdm

from database import SessionLocal, engine, Base  # noqa: E402
import models                                    # noqa: E402
from judge_engine import (                       # noqa: E402
    call_calibrated_judge,
    CalibratedJudgeResult,
    is_local_model,
)

# ── Logging Setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Model Name Normalization Helper ───────────────────────────────────────────
def get_calibrated_model_name(raw_model: str) -> str:
    """Return canonical model identifier with '_calibrated' suffix for DB storage."""
    m = raw_model.strip()
    # Map common aliases to canonical names
    canonical_map = {
        "gpt-4": "gpt-4o-mini",
        "gpt4": "gpt-4o-mini",
        "gpt-4o": "gpt-4o-mini",
        "gpt-4o-mini": "gpt-4o-mini",
        "deepseek": "deepseek/deepseek-chat",
        "deepseek-chat": "deepseek/deepseek-chat",
        "deepseek/deepseek-chat": "deepseek/deepseek-chat",
        "llama3": "meta-llama/llama-3.3-70b-instruct",
        "llama-3.3-70b": "meta-llama/llama-3.3-70b-instruct",
        "meta-llama/llama-3.3-70b-instruct": "meta-llama/llama-3.3-70b-instruct",
        "claude": "anthropic/claude-3-haiku",
        "claude-3-haiku": "anthropic/claude-3-haiku",
        "anthropic/claude-3-haiku": "anthropic/claude-3-haiku",
    }
    base_name = canonical_map.get(m, m)
    if not base_name.endswith("_calibrated"):
        return f"{base_name}_calibrated"
    return base_name


# ── CLI Argument Parser ───────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run batch calibrated Dual A/B Swap evaluations on benchmark data.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="Evaluator model identifier (e.g. gpt-4o-mini, deepseek/deepseek-chat).",
    )
    parser.add_argument(
        "--strategy",
        default="dual_ab",
        choices=["dual_ab", "verbosity_penalized", "none"],
        help="Bias mitigation strategy to apply.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Pause in seconds between API calls to satisfy rate limits.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of preferences to calibrate (for testing/partial runs).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch pending items and print status without calling LLM APIs.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-evaluate items even if calibrated records already exist in DB.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility.",
    )
    return parser.parse_args()


# ── Pending Items Fetcher ─────────────────────────────────────────────────────
def fetch_pending_calibration_preferences(
    db: Session,
    calibrated_model_name: str,
    limit: Optional[int] = None,
    force: bool = False,
) -> list[models.HumanPreference]:
    """
    Fetch HumanPreference records that have not yet been evaluated under the calibrated model identifier.
    """
    if force:
        stmt = select(models.HumanPreference).order_by(models.HumanPreference.id)
    else:
        already_judged_subq = (
            select(models.JudgeDecision.id)
            .where(
                models.JudgeDecision.prompt_id == models.HumanPreference.prompt_id,
                models.JudgeDecision.answer_a_id == models.HumanPreference.answer_a_id,
                models.JudgeDecision.answer_b_id == models.HumanPreference.answer_b_id,
                models.JudgeDecision.judge_model_name == calibrated_model_name,
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


# ── Decision Persistence Helper ───────────────────────────────────────────────
def save_calibrated_decision(
    db: Session,
    pref: models.HumanPreference,
    res: CalibratedJudgeResult,
    calibrated_model_name: str,
) -> models.JudgeDecision:
    """
    Map final calibrated verdict to DB winner_id and persist JudgeDecision record.
    """
    final_verdict = res.final_calibrated_winner
    if final_verdict == "A":
        winner_id = pref.answer_a_id
    elif final_verdict == "B":
        winner_id = pref.answer_b_id
    else:
        winner_id = None  # TIE or UNKNOWN

    decision = models.JudgeDecision(
        prompt_id=pref.prompt_id,
        judge_model_name=calibrated_model_name,
        answer_a_id=pref.answer_a_id,
        answer_b_id=pref.answer_b_id,
        position_a_id=pref.answer_a_id,
        winner_id=winner_id,
        reasoning=res.detailed_reasoning,
    )
    db.add(decision)
    db.commit()
    return decision


# ── Main Runner ───────────────────────────────────────────────────────────────
def run_batch_calibration(args: argparse.Namespace) -> None:
    calibrated_model_name = get_calibrated_model_name(args.model)
    raw_model_name = calibrated_model_name.replace("_calibrated", "")

    log.info("=" * 68)
    log.info("LLM-as-a-Judge Reliability Lab — Batch Calibration Runner")
    log.info("=" * 68)
    log.info("Target Model            : %s", raw_model_name)
    log.info("DB Calibrated Name      : %s", calibrated_model_name)
    log.info("Mitigation Strategy     : %s", args.strategy)
    log.info("API Delay               : %.1fs", args.delay)
    log.info("Limit                   : %s", args.limit or "All pending")
    log.info("Dry Run                 : %s", args.dry_run)
    log.info("Force Re-evaluation     : %s", args.force)

    random.seed(args.seed)

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        log.info("Fetching pending human_preferences for calibration ...")
        pending = fetch_pending_calibration_preferences(
            db, calibrated_model_name, limit=args.limit, force=args.force
        )

    total_pending = len(pending)
    log.info("%d preference matchup(s) pending calibration.", total_pending)

    if total_pending == 0:
        log.info("No pending matchups found for '%s'. Exiting.", calibrated_model_name)
        return

    if args.dry_run:
        log.info("Dry-run mode active. First 5 pending IDs: %s", [p.id for p in pending[:5]])
        log.info("Dry-run completed successfully.")
        return

    n_success = 0
    n_ties = 0
    n_bias_detected = 0
    n_errors = 0

    with SessionLocal() as db:
        pbar = tqdm(
            pending,
            total=total_pending,
            desc="Calibrating Dual A/B",
            unit="pair",
            dynamic_ncols=True,
        )

        for pref in pbar:
            prompt = db.get(models.Prompt, pref.prompt_id)
            ans_a = db.get(models.Answer, pref.answer_a_id)
            ans_b = db.get(models.Answer, pref.answer_b_id)

            if not prompt or not ans_a or not ans_b:
                log.warning("pref.id=%d missing prompt/answers. Skipping.", pref.id)
                n_errors += 1
                continue

            try:
                res = call_calibrated_judge(
                    question=prompt.text,
                    answer_a=ans_a.text,
                    answer_b=ans_b.text,
                    model_name=raw_model_name,
                    temperature=0.0,
                    mitigation_strategy=args.strategy,
                )

                save_calibrated_decision(db, pref, res, calibrated_model_name)

                n_success += 1
                if res.position_bias_detected:
                    n_bias_detected += 1
                if res.final_calibrated_winner in ("TIE", "UNKNOWN"):
                    n_ties += 1

                pbar.set_postfix(
                    ok=n_success,
                    flips=n_bias_detected,
                    ties=n_ties,
                    err=n_errors,
                )

            except Exception as exc:
                db.rollback()
                n_errors += 1
                log.error("pref.id=%d calibration error: %s", pref.id, exc)
                pbar.set_postfix(ok=n_success, err=n_errors)

            if args.delay > 0:
                time.sleep(args.delay)

    log.info("=" * 68)
    log.info("Batch Calibration Complete.")
    log.info("  ✅ Successful Calibrations : %d", n_success)
    log.info("  ⚠️  Position Flips Detected : %d", n_bias_detected)
    log.info("  ⚖️  Ties / Resolved Conflicts : %d", n_ties)
    log.info("  ❌ Errors / Skipped       : %d", n_errors)
    log.info("=" * 68)


if __name__ == "__main__":
    args = parse_args()
    run_batch_calibration(args)
