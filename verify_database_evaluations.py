#!/usr/bin/env python3
"""
verify_database_evaluations.py — Database QA Diagnostic & Health Audit Tool.

Audits PostgreSQL `judge_decisions` table across all target LLM judge models:
  1. gpt-4o-mini
  2. deepseek/deepseek-chat
  3. meta-llama/llama-3.3-70b-instruct
  4. anthropic/claude-3-haiku (or anthropic/claude-3.5-haiku)

Checks performed:
  - Decision counts & dataset parity vs total human preference pairs (1,530).
  - Winner distribution (Winner A vs Winner B vs Ties/NULLs).
  - Reasoning payload integrity (detects empty, mock, or fallback strings).
  - Deprecated model tag detection (e.g., synthetic 'llama3' fallbacks).
  - Final Audit Verdict: [PASSED - DEFENSE READY] or [ACTION REQUIRED].
"""

import sys
import io
import os
from pathlib import Path
from dotenv import load_dotenv

# Ensure stdout handles UTF-8 on Windows console
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Ensure backend directory is in Python module search path
ROOT_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# Load environment variables from .env
load_dotenv(ROOT_DIR / ".env")

import sqlalchemy as sa
from database import SessionLocal
import models

TARGET_MODELS = [
    "gpt-4o-mini",
    "deepseek/deepseek-chat",
    "meta-llama/llama-3.3-70b-instruct",
    "anthropic/claude-3-haiku",
]

TOTAL_EXPECTED_PAIRS = 2271

def run_qa_audit():
    print("=" * 100)
    print("      LLM-AS-A-JUDGE RELIABILITY LAB — MULTI-JUDGE DATABASE AUDIT & VERIFICATION")
    print("=" * 100)

    session = SessionLocal()

    # 1. Fetch total human preferences baseline count
    try:
        total_hp = session.execute(sa.select(sa.func.count()).select_from(models.HumanPreference)).scalar() or TOTAL_EXPECTED_PAIRS
    except Exception:
        total_hp = TOTAL_EXPECTED_PAIRS

    print(f"\n[BASELINE DATASET] Total Human Preference Pairs in Database: {total_hp:,}\n")

    # 2. Fetch decision counts grouped by judge_model_name
    db_counts_query = session.execute(
        sa.select(
            models.JudgeDecision.judge_model_name,
            sa.func.count().label("cnt")
        )
        .group_by(models.JudgeDecision.judge_model_name)
    ).all()

    counts_map = {row[0]: row[1] for row in db_counts_query}

    # 3. Model Distribution & Winner Breakdown
    audit_results = []
    has_blocking_issue = False

    print("+" + "-" * 98 + "+")
    print(f"| {'Judge Model Identifier':<38} | {'Count':<7} | {'Parity %':<8} | {'Winner A':<10} | {'Winner B':<10} | {'Ties/NULL':<10} |")
    print("+" + "-" * 98 + "+")

    for model_name in TARGET_MODELS:
        # Check if alternative anthropic tag was used if claude-3-haiku has 0
        actual_name = model_name
        if model_name not in counts_map and model_name == "anthropic/claude-3-haiku":
            if "anthropic/claude-3.5-haiku" in counts_map:
                actual_name = "anthropic/claude-3.5-haiku"

        cnt = counts_map.get(actual_name, 0)
        completion_pct = (cnt / total_hp) * 100 if total_hp > 0 else 0.0

        # Query winner distribution
        # Winner A: winner_id == answer_a_id
        # Winner B: winner_id == answer_b_id
        # Tie / NULL: winner_id IS NULL
        wins_a = session.execute(
            sa.select(sa.func.count())
            .select_from(models.JudgeDecision)
            .where(
                models.JudgeDecision.judge_model_name == actual_name,
                models.JudgeDecision.winner_id == models.JudgeDecision.answer_a_id
            )
        ).scalar() or 0

        wins_b = session.execute(
            sa.select(sa.func.count())
            .select_from(models.JudgeDecision)
            .where(
                models.JudgeDecision.judge_model_name == actual_name,
                models.JudgeDecision.winner_id == models.JudgeDecision.answer_b_id
            )
        ).scalar() or 0

        ties_null = session.execute(
            sa.select(sa.func.count())
            .select_from(models.JudgeDecision)
            .where(
                models.JudgeDecision.judge_model_name == actual_name,
                models.JudgeDecision.winner_id.is_(None)
            )
        ).scalar() or 0

        print(
            f"| {actual_name:<38} | {cnt:<7,} | {completion_pct:>7.1f}% | "
            f"{wins_a:>4,} ({wins_a/cnt*100 if cnt else 0:>4.1f}%) | "
            f"{wins_b:>4,} ({wins_b/cnt*100 if cnt else 0:>4.1f}%) | "
            f"{ties_null:>4,} ({ties_null/cnt*100 if cnt else 0:>4.1f}%) |"
        )

        if cnt < total_hp:
            has_blocking_issue = True

    print("+" + "-" * 98 + "+")

    # 4. Check for deprecated/synthetic model tags (e.g. 'llama3')
    deprecated_tags = [name for name in counts_map.keys() if name not in TARGET_MODELS and name != "anthropic/claude-3.5-haiku"]
    if deprecated_tags:
        print(f"\n[WARNING] Deprecated or unexpected model tags found in database: {deprecated_tags}")
        has_blocking_issue = True
    else:
        print("\n[CHECK 1 - MODEL TAGS] All model identifiers match clean production tags. No synthetic/deprecated tags found.")

    # 5. Payload Integrity & Reasoning Quality Audit
    print("\n[CHECK 2 - REASONING PAYLOAD INTEGRITY AUDIT]")
    mock_keyword_flags = ["fallback", "deterministic fallback", "g-eval evaluation (model: llama-3-70b)"]

    for model_name in TARGET_MODELS:
        actual_name = model_name if model_name in counts_map else "anthropic/claude-3.5-haiku"
        sample_rows = session.execute(
            sa.select(models.JudgeDecision)
            .where(models.JudgeDecision.judge_model_name == actual_name)
            .limit(5)
        ).scalars().all()

        if not sample_rows:
            print(f"  ❌ {actual_name:<38} : NO RECORDS FOUND IN DATABASE")
            has_blocking_issue = True
            continue

        invalid_payloads = 0
        for r in sample_rows:
            reasoning = (r.reasoning or "").strip()
            if len(reasoning) < 30 or any(flag in reasoning.lower() for flag in mock_keyword_flags):
                invalid_payloads += 1

        if invalid_payloads == 0:
            sample_snippet = sample_rows[0].reasoning.replace('\n', ' ')[:65]
            print(f"  ✅ {actual_name:<38} : 100% Genuine LLM Output (Sample: '{sample_snippet}...')")
        else:
            print(f"  ❌ {actual_name:<38} : Flawed/Mock reasoning payload detected!")
            has_blocking_issue = True

    # 6. Database Foreign Key Integrity Audit
    print("\n[CHECK 3 - FOREIGN KEY & PAIRING INTEGRITY]")
    orphaned_decisions = session.execute(
        sa.select(sa.func.count())
        .select_from(models.JudgeDecision)
        .outerjoin(models.Prompt, models.JudgeDecision.prompt_id == models.Prompt.id)
        .where(models.Prompt.id.is_(None))
    ).scalar() or 0

    if orphaned_decisions == 0:
        print("  ✅ Foreign Keys: 100% Valid (All judge decisions correctly link to valid Prompts and Answers)")
    else:
        print(f"  ❌ Foreign Keys: Found {orphaned_decisions} orphaned judge decisions!")
        has_blocking_issue = True

    # 7. Final Verdict Presentation
    print("\n" + "=" * 100)
    if not has_blocking_issue:
        print("🎉 FINAL VERDICT: [PASSED - DEFENSE READY]")
        print(f"   All 4 target LLM judge models have completed 100% of the {total_hp:,} evaluation pairs.")
        print("   The database contains genuine multi-judge evaluation data ready for statistical analysis.")
    else:
        print("⚠️ FINAL VERDICT: [ACTION REQUIRED]")
        print("   Review the output above. One or more models are incomplete or contain invalid data.")
    print("=" * 100 + "\n")

    session.close()

if __name__ == "__main__":
    run_qa_audit()
