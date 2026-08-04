"""
db_audit.py
===========
Standalone diagnostic script.
Audits the PostgreSQL judge_decisions table to determine whether:
  - Calibrated (dual A/B swap) evaluation records are present.
  - Multi-judge ensemble evaluation records are present.
  - Standard baseline single-pass records are the only contents.
  - Position swap data is populated (position_a_id != answer_a_id).
"""

import sys
import os
from pathlib import Path

# ── Path Setup ────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/judgelab")

print("Connecting to:", DATABASE_URL.replace(DATABASE_URL.split("@")[-1], "***"))

engine = create_engine(DATABASE_URL, connect_args={"connect_timeout": 5})

SEP = "=" * 72

try:
    with engine.connect() as conn:

        print(f"\n{SEP}")
        print("  DATABASE AUDIT — judge_decisions TABLE")
        print(SEP)

        # ── 1. Public table listing ───────────────────────────────────────────
        tables = conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name;"
        )).fetchall()
        print("\n[1] PUBLIC TABLES IN DATABASE:")
        for t in tables:
            print(f"    - {t[0]}")

        # ── 2. Total row count ────────────────────────────────────────────────
        total = conn.execute(text("SELECT COUNT(*) FROM judge_decisions")).scalar()
        print(f"\n[2] TOTAL judge_decisions rows: {total:,}")

        # ── 3. Column schema ─────────────────────────────────────────────────
        cols = conn.execute(text(
            "SELECT column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_name = 'judge_decisions' "
            "ORDER BY ordinal_position;"
        )).fetchall()
        print("\n[3] COLUMN SCHEMA of judge_decisions:")
        for c in cols:
            print(f"    {c[0]:<25} {c[1]:<20} nullable={c[2]}")

        # ── 4. Row breakdown by judge_model_name ──────────────────────────────
        breakdown = conn.execute(text(
            "SELECT judge_model_name, COUNT(*) AS cnt "
            "FROM judge_decisions "
            "GROUP BY judge_model_name "
            "ORDER BY cnt DESC;"
        )).fetchall()
        print("\n[4] RECORDS BY judge_model_name:")
        if breakdown:
            for row in breakdown:
                print(f"    {str(row[0]):<45} {int(row[1]):>8,} rows")
        else:
            print("    (no rows found)")

        # ── 5. Row breakdown by prompt category ───────────────────────────────
        cat_breakdown = conn.execute(text(
            "SELECT p.category, COUNT(jd.id) AS cnt "
            "FROM judge_decisions jd "
            "JOIN prompts p ON jd.prompt_id = p.id "
            "GROUP BY p.category "
            "ORDER BY cnt DESC;"
        )).fetchall()
        print("\n[5] RECORDS BY prompt.category (key: live/live_calibrated/ensemble_eval/benchmark):")
        categories_found = []
        if cat_breakdown:
            for row in cat_breakdown:
                categories_found.append(str(row[0]))
                print(f"    {str(row[0]):<40} {int(row[1]):>8,} rows")
        else:
            print("    (no rows found)")

        # ── 6. Position swap detection ────────────────────────────────────────
        swap_count = conn.execute(text(
            "SELECT COUNT(*) FROM judge_decisions "
            "WHERE position_a_id IS NOT NULL AND position_a_id != answer_a_id;"
        )).scalar()
        total_with_pos = conn.execute(text(
            "SELECT COUNT(*) FROM judge_decisions WHERE position_a_id IS NOT NULL;"
        )).scalar()
        normal_count = conn.execute(text(
            "SELECT COUNT(*) FROM judge_decisions "
            "WHERE position_a_id IS NOT NULL AND position_a_id = answer_a_id;"
        )).scalar()
        null_pos = conn.execute(text(
            "SELECT COUNT(*) FROM judge_decisions WHERE position_a_id IS NULL;"
        )).scalar()

        print(f"\n[6] POSITION SWAP ANALYSIS (position_a_id tracking):")
        print(f"    Rows with position_a_id populated    : {total_with_pos:,}")
        print(f"    Rows with position_a_id NULL         : {null_pos:,}")
        print(f"    SWAPPED presentations (B shown first): {swap_count:,}")
        print(f"    Normal presentations (A shown first) : {normal_count:,}")
        if total_with_pos > 0:
            pct = swap_count / total_with_pos * 100
            print(f"    Swap rate                            : {pct:.1f}%  (expect ~50% for randomised batch runs)")

        # ── 7. Calibrated / ensemble event count ──────────────────────────────
        calibrated_rows = conn.execute(text(
            "SELECT COUNT(*) FROM judge_decisions jd "
            "JOIN prompts p ON jd.prompt_id = p.id "
            "WHERE p.category = 'live_calibrated';"
        )).scalar()
        ensemble_rows = conn.execute(text(
            "SELECT COUNT(*) FROM judge_decisions jd "
            "JOIN prompts p ON jd.prompt_id = p.id "
            "WHERE p.category = 'ensemble_eval';"
        )).scalar()
        live_rows = conn.execute(text(
            "SELECT COUNT(*) FROM judge_decisions jd "
            "JOIN prompts p ON jd.prompt_id = p.id "
            "WHERE p.category = 'live';"
        )).scalar()
        benchmark_rows = conn.execute(text(
            "SELECT COUNT(*) FROM judge_decisions jd "
            "JOIN prompts p ON jd.prompt_id = p.id "
            "WHERE p.category NOT IN ('live', 'live_calibrated', 'ensemble_eval');"
        )).scalar()

        print(f"\n[7] EVALUATION TYPE BREAKDOWN:")
        print(f"    Benchmark (ingested batch, baseline)  : {benchmark_rows:,}")
        print(f"    Live single-pass (standard)           : {live_rows:,}")
        print(f"    Live calibrated (dual A/B swap)       : {calibrated_rows:,}")
        print(f"    Live ensemble (multi-judge voting)    : {ensemble_rows:,}")

        # ── 8. Human preferences aligned count ───────────────────────────────
        hp_count = conn.execute(text("SELECT COUNT(*) FROM human_preferences")).scalar()
        prompts_count = conn.execute(text("SELECT COUNT(*) FROM prompts")).scalar()
        answers_count = conn.execute(text("SELECT COUNT(*) FROM answers")).scalar()
        print(f"\n[8] RELATED TABLE COUNTS:")
        print(f"    prompts                               : {prompts_count:,}")
        print(f"    answers                               : {answers_count:,}")
        print(f"    human_preferences (gold labels)       : {hp_count:,}")
        print(f"    judge_decisions   (total)             : {total:,}")

        # ── 9. Sample of 5 most recent rows ──────────────────────────────────
        recent = conn.execute(text(
            "SELECT jd.id, jd.judge_model_name, p.category, "
            "jd.answer_a_id, jd.position_a_id, jd.winner_id, "
            "LEFT(jd.reasoning, 80) AS snippet "
            "FROM judge_decisions jd "
            "JOIN prompts p ON jd.prompt_id = p.id "
            "ORDER BY jd.id DESC LIMIT 5;"
        )).fetchall()
        print(f"\n[9] MOST RECENT 5 judge_decisions ROWS:")
        for row in recent:
            swapped_flag = "(B-FIRST)" if row[4] != row[3] else "(A-FIRST)"
            print(f"    id={row[0]} | model={row[1]} | cat={row[2]} | {swapped_flag} | winner_id={row[5]}")
            print(f"         reasoning: {row[6]}...")

        # ── FINAL VERDICT ─────────────────────────────────────────────────────
        print(f"\n{SEP}")
        print("  DIAGNOSTIC VERDICT")
        print(SEP)

        verdict_lines = []

        if total == 0:
            verdict_lines.append("CRITICAL: judge_decisions table is EMPTY. No evaluations have been run.")
        else:
            verdict_lines.append(f"OK: {total:,} total evaluation records exist in judge_decisions.")

        if benchmark_rows > 0:
            verdict_lines.append(f"OK: {benchmark_rows:,} BASELINE benchmark evaluation records found (ingested batch).")
        else:
            verdict_lines.append("WARN: No ingested benchmark evaluation records. run_evaluation.py has not been executed.")

        if calibrated_rows > 0:
            verdict_lines.append(f"OK: {calibrated_rows:,} CALIBRATED (dual A/B swap) live records found in DB.")
        else:
            verdict_lines.append("WARN: ZERO calibrated dual A/B swap records in DB. These only accumulate via manual Live Lab usage.")

        if ensemble_rows > 0:
            verdict_lines.append(f"OK: {ensemble_rows:,} ENSEMBLE (multi-judge) live records found in DB.")
        else:
            verdict_lines.append("WARN: ZERO ensemble evaluation records in DB. These only accumulate via manual Live Lab usage.")

        if swap_count > 0 and total_with_pos > 0:
            pct_s = swap_count / total_with_pos * 100
            verdict_lines.append(
                f"OK: Presentation-order swapping is ACTIVE — {pct_s:.1f}% of records used B-first ordering "
                f"({swap_count:,} rows). position_a_id field is correctly populated."
            )
        elif total > 0:
            verdict_lines.append(
                "WARN: position_a_id == answer_a_id in ALL rows — presentation order was never randomised "
                "during ingestion, OR all live evals happened to run A-first."
            )

        print()
        for line in verdict_lines:
            prefix = "  [!]" if line.startswith("WARN") or line.startswith("CRITICAL") else "  [✓]"
            print(f"{prefix} {line}")

        # ── MACRO MITIGATION CONCLUSION ───────────────────────────────────────
        print()
        print("  MACRO MITIGATION IMPLICATION:")
        if calibrated_rows == 0 and ensemble_rows == 0:
            print("  [!] NO empirical batch-debiased evaluation records exist in PostgreSQL.")
            print("  [!] GET /api/stats/macro-benchmark is CURRENTLY falling back to")
            print("      hardcoded +0.212 delta-kappa and +0.179 delta-accuracy numbers.")
            print("  [!] A batch calibrated evaluation run is REQUIRED to produce real")
            print("      before/after comparison data from actual debiased verdicts.")
        else:
            print("  [✓] Empirical debiased evaluation data IS present in the database.")
            print("  [✓] Macro benchmark synthesis CAN be computed from real records.")

        print(f"\n{SEP}\n")

except Exception as e:
    print(f"\n[FATAL] Database connection or query failed: {e}")
    print("Check that PostgreSQL is running and DATABASE_URL is correct.")
    sys.exit(1)
