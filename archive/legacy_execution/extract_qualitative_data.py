"""
extract_qualitative_data.py
===========================
Stratified Qualitative Data Extraction for LLM-as-a-Judge study.

Performs qualitative categorization of aligned evaluations into 4 research buckets:
  - Bucket A (Verbosity Bias): AI chose a longer answer (>50 words diff) while human chose shorter/tie.
  - Bucket B (Forced-Choice Hallucinations): Human choice was a Tie, but AI chose a winner.
  - Bucket C (Position Bias): AI chose the answer in Position B.
  - Bucket D (Baseline Alignment): AI choice matched human choice.

Outputs stratified CSV files to the root directory's `qualitative_data/` folder.

Usage:
    python backend/extract_qualitative_data.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


# ── path setup ────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# Load environment variables
load_dotenv(ROOT_DIR / ".env")

# Database URL
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/judgelab"
)


def get_connection_engine():
    """Create database engine from DATABASE_URL env var."""
    return create_engine(DATABASE_URL)


def fetch_enriched_data(engine, judge_model_name: str = "gpt-4o-mini") -> pd.DataFrame:
    """Fetch matched judgments joined with prompts and answers for a given judge model."""
    sql_query = text("""
    SELECT 
        hp.winner_id as human_winner_id,
        hp.answer_a_id,
        hp.answer_b_id,
        jd.winner_id as llm_winner_id,
        jd.position_a_id,
        jd.reasoning as reasoning_text,
        p.id as prompt_id,
        a1.word_count as answer_a_word_count,
        a2.word_count as answer_b_word_count,
        a1.model_name as answer_a_model_name,
        a2.model_name as answer_b_model_name
    FROM human_preferences hp
    JOIN judge_decisions jd 
        ON hp.prompt_id = jd.prompt_id 
        AND hp.answer_a_id = jd.answer_a_id 
        AND hp.answer_b_id = jd.answer_b_id
    JOIN prompts p ON hp.prompt_id = p.id
    JOIN answers a1 ON hp.answer_a_id = a1.id
    JOIN answers a2 ON hp.answer_b_id = a2.id
    WHERE jd.judge_model_name = :judge_model_name;
    """)
    with engine.connect() as conn:
        df = pd.read_sql_query(sql_query, conn, params={"judge_model_name": judge_model_name})
    return df


def stratify_data(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Categorize records into the four qualitative analysis buckets."""
    # Ensure reasoning text handles NULLs gracefully
    df["reasoning_text"] = df["reasoning_text"].fillna("")

    # Map winner choices to categorical 'A', 'B', or 'Tie'
    def get_choice(winner_id, answer_a_id, answer_b_id):
        if pd.isna(winner_id):
            return "Tie"
        elif winner_id == answer_a_id:
            return "A"
        elif winner_id == answer_b_id:
            return "B"
        return "Unknown"

    df["human_winner"] = df.apply(
        lambda r: get_choice(r["human_winner_id"], r["answer_a_id"], r["answer_b_id"]), axis=1
    )
    df["ai_winner"] = df.apply(
        lambda r: get_choice(r["llm_winner_id"], r["answer_a_id"], r["answer_b_id"]), axis=1
    )

    # Word count difference (len(A) - len(B))
    df["word_count_diff"] = df["answer_a_word_count"] - df["answer_b_word_count"]
    
    # Model names formatting
    df["model_names"] = df.apply(
        lambda r: f"{r['answer_a_model_name']} vs {r['answer_b_model_name']}", axis=1
    )

    # Prepare export DataFrame structure
    cols_to_export = [
        "prompt_id",
        "reasoning_text",
        "word_count_diff",
        "human_winner",
        "ai_winner",
        "model_names",
    ]

    buckets = {}

    # --- Bucket A: Verbosity-Biased Cases ---
    # Cases where the AI chose the longer answer (difference > 50 words)
    # while the human chose the shorter one or declared a tie.
    def is_verbosity_biased(row):
        # AI chose A, A is longer by > 50, Human chose B or Tie
        cond_a = (
            row["ai_winner"] == "A"
            and row["word_count_diff"] > 50
            and row["human_winner"] in ["B", "Tie"]
        )
        # AI chose B, B is longer by > 50, Human chose A or Tie
        cond_b = (
            row["ai_winner"] == "B"
            and row["word_count_diff"] < -50
            and row["human_winner"] in ["A", "Tie"]
        )
        return cond_a or cond_b

    df_a = df[df.apply(is_verbosity_biased, axis=1)]
    buckets["qualitative_verbosity"] = df_a[cols_to_export]

    # --- Bucket B: Forced-Choice Hallucinations ---
    # Human rater declared a 'Tie', but LLM Judge forced a win (A or B).
    df_b = df[(df["human_winner"] == "Tie") & (df["ai_winner"].isin(["A", "B"]))]
    buckets["qualitative_forced_choice"] = df_b[cols_to_export]

    # --- Bucket C: Position-Bias Cases ---
    # AI chose Position B (second model shown in randomized prompt).
    def is_position_b_chosen(row):
        if row["llm_winner_id"] is None:
            return False
        # If position_a_id matches answer_a_id, then Position B is answer_b_id.
        if row["position_a_id"] == row["answer_a_id"]:
            pos_b_id = row["answer_b_id"]
        else:
            pos_b_id = row["answer_a_id"]
        return row["llm_winner_id"] == pos_b_id

    df_c = df[df.apply(is_position_b_chosen, axis=1)]
    buckets["qualitative_position_bias"] = df_c[cols_to_export]

    # --- Bucket D: Baseline Alignment ---
    # AI Judge matched human choice (A vs A, B vs B, Tie vs Tie).
    df_d = df[df["human_winner"] == df["ai_winner"]]
    buckets["qualitative_baseline_alignment"] = df_d[cols_to_export]

    return buckets


def main() -> None:
    parser = argparse.ArgumentParser(description="Qualitative Data Stratifier")
    parser.add_argument("--model", type=str, default="gpt-4o-mini", help="Judge model name to extract")
    args = parser.parse_args()

    judge_model = args.model

    print("=" * 65)
    print(f"  LLM-as-a-Judge Reliability Lab - Qualitative Data Stratifier ({judge_model})")
    print("=" * 65)

    engine = get_connection_engine()
    df = fetch_enriched_data(engine, judge_model_name=judge_model)

    if df.empty:
        print(f"No evaluation records found matching '{judge_model}'.")
        return


    print(f"Total rows retrieved: {len(df)}")
    buckets = stratify_data(df)

    # Ensure output folder exists at the root and model-specific subdir
    output_dir = ROOT_DIR / "qualitative_data"
    output_dir.mkdir(parents=True, exist_ok=True)

    sanitized_model = judge_model.replace("/", "_")
    model_output_dir = output_dir / sanitized_model
    model_output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory (model-specific): {model_output_dir.resolve()}\n")

    # Export each bucket to the model-specific subdirectory
    print(f"{'CSV Filename':<30} | {'Rows Count':<12}")
    print(f"{'-'*30}-+-{'-'*12}")
    for name, b_df in buckets.items():
        filename = f"{name}.csv"
        # Primary: model-specific subdir
        filepath = model_output_dir / filename
        b_df.to_csv(filepath, index=False, encoding="utf-8")
        print(f"{filename:<30} | {len(b_df):<12,}")

    # Backwards-compat: also write to root qualitative_data/ for gpt-4o-mini
    # so existing /api/qualitative/{bucket} calls without judge_model still work
    if judge_model == "gpt-4o-mini":
        for name, b_df in buckets.items():
            root_path = output_dir / f"{name}.csv"
            b_df.to_csv(root_path, index=False, encoding="utf-8")

    print("\nExtraction complete! OK")
    print("=" * 65)



if __name__ == "__main__":
    main()
