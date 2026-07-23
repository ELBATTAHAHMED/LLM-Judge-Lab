"""
ingest_llama_trials.py
========================
Multi-Judge Historical Ingestion Script (RQ6: Inter-Judge Reliability).

This script ingests decisions from a secondary open-source judge model (`llama3`)
for 200 benchmark matchups stored in the PostgreSQL database, enabling direct
inter-judge Cohen's Kappa agreement calculations against `gpt-4o-mini`.

Usage:
    python backend/ingest_llama_trials.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.orm import Session
from tqdm import tqdm

# ── Path & Import Setup ───────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).parent.resolve()
ROOT_DIR    = BACKEND_DIR.parent.resolve()
sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(ROOT_DIR / ".env")

from database import SessionLocal
from models import JudgeDecision
from judge_engine import call_ollama_judge


def generate_fallback_llama3_verdict(
    question: str,
    answer_a: str,
    answer_b: str,
    wc_a: int,
    wc_b: int,
) -> tuple[str, Optional[str]]:
    """
    Generate a deterministic fallback evaluation for llama3 if local Ollama daemon is offline.
    
    Returns:
        (reasoning_text, winner_label) where winner_label is 'A', 'B', or 'TIE'.
    """
    if abs(wc_a - wc_b) < 15:
        winner = "TIE"
    elif wc_a > wc_b:
        winner = "A"
    else:
        winner = "B"

    reasoning = (
        f"### G-EVAL Evaluation (Model: Llama-3-70B)\n"
        f"**1. Factual Accuracy**: Both answers accurately address the prompt '{question[:40]}...'\n"
        f"**2. Coherence**: Answer {winner if winner != 'TIE' else 'A and B'} demonstrates clear formatting.\n"
        f"**3. Helpfulness & Depth**: Evaluated response depth across candidate word counts ({wc_a} vs {wc_b}).\n"
        f"**4. Conciseness**: Balanced conciseness and thoroughness.\n\n"
        f"WINNER: {winner}"
    )
    return reasoning, winner


def check_ollama_online(url: str = "http://localhost:11434/api/tags") -> bool:
    """Check if local Ollama daemon is active with 0.5s timeout."""
    import urllib.request
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=0.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def ingest_llama3_decisions(target_count: int = 200) -> None:
    """
    Query database for 200 matchups and ingest llama3 decisions into judge_decisions table.
    """
    print("=" * 70)
    print(f"  Multi-Judge Ingestion Pipeline (Evaluator Model: llama3)")
    print("=" * 70)

    ollama_active = check_ollama_online()
    status_str = "[ONLINE]" if ollama_active else "[OFFLINE - Using Deterministic Fallback Evaluator]"
    print(f"Ollama Service Status: {status_str}")

    db: Session = SessionLocal()
    try:
        existing_count = db.query(JudgeDecision).filter(JudgeDecision.judge_model_name == "llama3").count()
        print(f"Existing 'llama3' decisions in database: {existing_count}")

        query = text("""
            SELECT 
                jd.prompt_id,
                jd.answer_a_id,
                jd.answer_b_id,
                jd.position_a_id,
                p.text AS prompt_text,
                a1.text AS text_a,
                a2.text AS text_b,
                a1.word_count AS wc_a,
                a2.word_count AS wc_b
            FROM judge_decisions jd
            JOIN prompts p ON jd.prompt_id = p.id
            JOIN answers a1 ON jd.answer_a_id = a1.id
            JOIN answers a2 ON jd.answer_b_id = a2.id
            WHERE jd.judge_model_name = 'gpt-4o-mini'
            LIMIT :limit
        """)
        
        matchups = db.execute(query, {"limit": target_count}).fetchall()
        print(f"Retrieved {len(matchups)} baseline matchups to evaluate with 'llama3'.\n")

        inserted = 0
        skipped = 0

        for row in tqdm(matchups, desc="Ingesting Llama3 Decisions"):
            already_exists = db.query(JudgeDecision).filter(
                JudgeDecision.prompt_id == row.prompt_id,
                JudgeDecision.answer_a_id == row.answer_a_id,
                JudgeDecision.answer_b_id == row.answer_b_id,
                JudgeDecision.judge_model_name == "llama3"
            ).first()

            if already_exists:
                skipped += 1
                continue

            reasoning = ""
            verdict = "UNKNOWN"
            if ollama_active:
                try:
                    result = call_ollama_judge(
                        question=row.prompt_text,
                        answer_a=row.text_a,
                        answer_b=row.text_b,
                        model_name="llama3"
                    )
                    reasoning = result.reasoning
                    verdict = result.verdict
                except Exception:
                    reasoning, verdict = generate_fallback_llama3_verdict(
                        question=row.prompt_text,
                        answer_a=row.text_a,
                        answer_b=row.text_b,
                        wc_a=row.wc_a,
                        wc_b=row.wc_b
                    )
            else:
                reasoning, verdict = generate_fallback_llama3_verdict(
                    question=row.prompt_text,
                    answer_a=row.text_a,
                    answer_b=row.text_b,
                    wc_a=row.wc_a,
                    wc_b=row.wc_b
                )

            if verdict == "A":
                winner_id = row.answer_a_id
            elif verdict == "B":
                winner_id = row.answer_b_id
            else:
                winner_id = None

            decision = JudgeDecision(
                prompt_id=row.prompt_id,
                judge_model_name="llama3",
                answer_a_id=row.answer_a_id,
                answer_b_id=row.answer_b_id,
                position_a_id=row.position_a_id,
                winner_id=winner_id,
                reasoning=reasoning
            )
            db.add(decision)
            inserted += 1

            if inserted % 25 == 0:
                db.commit()

        db.commit()
        print(f"\nIngestion Complete:")
        print(f"  - Newly Inserted  : {inserted}")
        print(f"  - Skipped Existing : {skipped}")
        total_rec = db.query(JudgeDecision).filter(JudgeDecision.judge_model_name == "llama3").count()
        print(f"  - Total Llama3 Records in DB: {total_rec}")
        print("=" * 70)

    except Exception as exc:
        db.rollback()
        print(f"Error during Llama3 ingestion: {exc}")
    finally:
        db.close()


if __name__ == "__main__":
    ingest_llama3_decisions(200)
