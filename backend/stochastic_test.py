"""
stochastic_test.py
===================
Empirical Stochastic Consistency Analysis Module (RQ2).

Evaluates the variance and self-consistency of an LLM evaluator judge
by running repeated empirical evaluation trials on prompt pairs drawn from the
2,271 Vicuna human preference benchmark dataset using gpt-4o-mini at
temperature=0.0 (and T=0.7) via the OpenAI API.

Outputs:
  - `qualitative_data/stochastic_consistency_real.csv`
  - `qualitative_data/stochastic_consistency.csv`
  - Console summary report
"""

from __future__ import annotations

import hashlib
import os
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from sqlalchemy import text

# Path Setup
BACKEND_DIR = Path(__file__).parent.resolve()
ROOT_DIR = BACKEND_DIR.parent.resolve()
sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(ROOT_DIR / ".env")
QUALITATIVE_DIR = ROOT_DIR / "qualitative_data"

from database import engine
from judge_engine import call_judge


def load_evaluation_pairs(sample_size: int = 30, seed: int = 42) -> pd.DataFrame:
    """Load a deterministic subset of evaluation pairs from DB or local CSV dataset."""
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT hp.id as pair_id, p.id as prompt_id, p.text as question,
                       a1.text as answer_a, a2.text as answer_b,
                       a1.id as answer_a_id, a2.id as answer_b_id,
                       hp.winner_id as human_winner_id
                FROM human_preferences hp
                JOIN prompts p ON hp.prompt_id = p.id
                JOIN answers a1 ON hp.answer_a_id = a1.id
                JOIN answers a2 ON hp.answer_b_id = a2.id
                ORDER BY hp.id
            """)
            df = pd.read_sql(query, conn)
            if len(df) > 0:
                print(f"Loaded {len(df)} pairs from PostgreSQL database.")
                return df.sample(n=min(sample_size, len(df)), random_state=seed).reset_index(drop=True)
    except Exception as exc:
        print(f"Database fetch notice: {exc}. Falling back to CSV dataset.")

    csv_path = QUALITATIVE_DIR / "qualitative_baseline_alignment.csv"
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        if "reasoning_text" in df.columns and "question" not in df.columns:
            df = df.rename(columns={"reasoning_text": "question"})
        return df.sample(n=min(sample_size, len(df)), random_state=seed).reset_index(drop=True)

    raise FileNotFoundError("Could not load evaluation pairs from Database or local CSV.")


def run_stochastic_consistency_test(
    sample_size: int = 30,
    repeats: int = 5,
    temperature: float = 0.0,
    model_name: str = "gpt-4o-mini",
    max_workers: int = 10,
):
    """
    Run N repeated empirical API evaluation trials per pair to compute true stochastic flip rate.
    """
    print("=========================================================")
    print(" Starting Empirical Stochastic Consistency Analysis (RQ2)")
    print(f" Sample Size: {sample_size} pairs | Repeats per Pair: {repeats} | T = {temperature}")
    print(f" Model: {model_name} | Parallel Workers: {max_workers}")
    print("=========================================================")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is missing in .env.")

    client = OpenAI(api_key=api_key)
    sample_df = load_evaluation_pairs(sample_size=sample_size, seed=42)

    def evaluate_single_trial(prompt_id, question, answer_a, answer_b, trial_idx):
        for attempt in range(3):
            try:
                res = call_judge(
                    client=client,
                    question=question,
                    answer_a=answer_a,
                    answer_b=answer_b,
                    model_name=model_name,
                    temperature=temperature,
                )
                reasoning_hash = hashlib.sha256(res.reasoning.encode("utf-8")).hexdigest()[:12]
                return {
                    "prompt_id": prompt_id,
                    "trial_index": trial_idx,
                    "temperature": temperature,
                    "winner_id": res.verdict,
                    "reasoning_hash": reasoning_hash,
                    "reasoning_preview": res.reasoning[:100].replace("\n", " "),
                }
            except Exception as exc:
                print(f"Trial {trial_idx} for prompt #{prompt_id} warning: {exc}. Retrying in 2s...")
                time.sleep(2)

        return {
            "prompt_id": prompt_id,
            "trial_index": trial_idx,
            "temperature": temperature,
            "winner_id": "UNKNOWN",
            "reasoning_hash": "error",
            "reasoning_preview": "Error",
        }

    # Dispatch tasks across ThreadPoolExecutor
    futures = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for idx, row in sample_df.iterrows():
            prompt_id = int(row.get("prompt_id", idx + 1))
            question = str(row.get("question", row.get("reasoning_text", "Evaluate responses")))
            answer_a = str(row.get("answer_a", "Candidate A response text"))
            answer_b = str(row.get("answer_b", "Candidate B response text"))

            for r in range(repeats):
                futures.append(
                    executor.submit(
                        evaluate_single_trial,
                        prompt_id,
                        question,
                        answer_a,
                        answer_b,
                        r,
                    )
                )

        raw_trial_results = []
        for future in as_completed(futures):
            raw_trial_results.append(future.result())

    trials_df = pd.DataFrame(raw_trial_results)

    # Compute modal (majority) verdict and is_flipped flag per prompt_id
    summary_records = []
    detailed_records = []

    total_flipped_trials = 0
    pairs_with_flips = 0

    for prompt_id, group in trials_df.groupby("prompt_id"):
        winners = group["winner_id"].tolist()
        counts = Counter(winners)
        modal_winner, modal_count = counts.most_common(1)[0]

        pair_flips = 0
        for _, row in group.iterrows():
            is_flipped = bool(row["winner_id"] != modal_winner)
            if is_flipped:
                pair_flips += 1
                total_flipped_trials += 1

            detailed_records.append({
                "prompt_id": prompt_id,
                "trial_index": row["trial_index"],
                "temperature": row["temperature"],
                "winner_id": row["winner_id"],
                "reasoning_hash": row["reasoning_hash"],
                "is_flipped": is_flipped,
            })

        flip_rate_pct = round((pair_flips / len(group)) * 100, 1)
        consensus_pct = round((modal_count / len(group)) * 100, 1)
        if pair_flips > 0:
            pairs_with_flips += 1

        summary_records.append({
            "prompt_id": prompt_id,
            "majority_verdict": modal_winner,
            "majority_consensus_pct": consensus_pct,
            "flip_rate": flip_rate_pct,
            "trial_verdicts": "|".join(winners),
        })

    real_csv_df = pd.DataFrame(detailed_records).sort_values(by=["prompt_id", "trial_index"])
    summary_df = pd.DataFrame(summary_records).sort_values(by="prompt_id")

    # Exports
    real_csv_path = QUALITATIVE_DIR / "stochastic_consistency_real.csv"
    summary_csv_path = QUALITATIVE_DIR / "stochastic_consistency.csv"

    QUALITATIVE_DIR.mkdir(parents=True, exist_ok=True)
    real_csv_df.to_csv(real_csv_path, index=False)
    summary_df.to_csv(summary_csv_path, index=False)

    mean_flip_rate = summary_df["flip_rate"].mean()
    mean_consensus = summary_df["majority_consensus_pct"].mean()

    print("\nEmpirical Stochastic Consistency Results (RQ2 - Real API Data):")
    print("---------------------------------------------------------")
    print(f"  Total Pairs Evaluated   : {len(summary_df)}")
    print(f"  Repeated Trials per Pair: {repeats}")
    print(f"  Total API Calls Made    : {len(real_csv_df)}")
    print(f"  Mean Majority Consensus : {mean_consensus:.2f}%")
    print(f"  Stochastic Flip Rate    : {mean_flip_rate:.2f}%")
    print(f"  Pairs with Inconsistency: {pairs_with_flips} / {len(summary_df)}")
    print("---------------------------------------------------------")
    print(f" Saved detailed trial data to: {real_csv_path}")
    print(f" Saved summary consistency to: {summary_csv_path}")


def parse_args():
    import argparse
    parser = argparse.ArgumentParser(
        description="Run empirical stochastic consistency test (RQ2).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--sample-size", type=int, default=30, help="Number of prompt pairs to sample")
    parser.add_argument("--repeats", type=int, default=5, help="Number of repeated trials per pair")
    parser.add_argument("--temperature", type=float, default=0.0, help="Sampling temperature")
    parser.add_argument("--model", default="gpt-4o-mini", help="Judge model identifier")
    parser.add_argument("--max-workers", type=int, default=10, help="Maximum concurrent thread workers")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_stochastic_consistency_test(
        sample_size=args.sample_size,
        repeats=args.repeats,
        temperature=args.temperature,
        model_name=args.model,
        max_workers=args.max_workers,
    )

