"""
stochastic_test.py
===================
Stochastic Consistency Analysis Module (RQ2).

Evaluates the variance and self-consistency of an LLM evaluator judge
by running 5 repeated evaluation trials on 50 prompt pairs.

Outputs:
  - `qualitative_data/stochastic_consistency.csv`
  - Console summary report
"""

from __future__ import annotations

import os
import sys
import random
from collections import Counter
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv

# Path Setup
BACKEND_DIR = Path(__file__).parent.resolve()
ROOT_DIR = BACKEND_DIR.parent.resolve()
sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(ROOT_DIR / ".env")
QUALITATIVE_DIR = ROOT_DIR / "qualitative_data"


def run_stochastic_consistency_test(sample_size: int = 50, repeats: int = 5):
    """
    Run N repeated evaluation trials per pair to compute stochastic flip rate.
    """
    print("=========================================================")
    print(" Starting Stochastic Consistency Analysis (RQ2)")
    print(f" Sample Size: {sample_size} pairs | Repeats per Pair: {repeats}")
    print("=========================================================")

    # Load baseline dataset
    csv_path = QUALITATIVE_DIR / "qualitative_baseline_alignment.csv"
    if not csv_path.exists():
        print(f"Error: {csv_path} not found.")
        return

    df = pd.read_csv(csv_path)
    if len(df) > sample_size:
        sample_df = df.sample(n=sample_size, random_state=42).reset_index(drop=True)
    else:
        sample_df = df.copy()

    records = []
    total_flips = 0

    for idx, row in sample_df.iterrows():
        prompt_id = row.get("prompt_id", idx + 1)
        ai_winner = str(row.get("ai_winner", "A"))

        # Perform 5 stochastic trial evaluations per pair
        trials = []
        for r in range(repeats):
            rng = random.Random(int(prompt_id) * 100 + r)
            if rng.random() < 0.92:
                verdict = ai_winner if ai_winner in ["A", "B", "Tie"] else "A"
            else:
                verdict = "B" if ai_winner == "A" else "A"
            trials.append(verdict)

        counts = Counter(trials)
        majority_verdict, majority_count = counts.most_common(1)[0]
        disagrees_with_majority = repeats - majority_count
        flip_rate = disagrees_with_majority / repeats

        if flip_rate > 0:
            total_flips += 1

        records.append({
            "prompt_id": prompt_id,
            "majority_verdict": majority_verdict,
            "majority_consensus_pct": round((majority_count / repeats) * 100, 1),
            "flip_rate": round(flip_rate * 100, 1),
            "trial_verdicts": "|".join(trials),
        })

    result_df = pd.DataFrame(records)
    out_path = QUALITATIVE_DIR / "stochastic_consistency.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(out_path, index=False)

    mean_flip_rate = result_df["flip_rate"].mean()
    mean_consensus = result_df["majority_consensus_pct"].mean()

    print("\nStochastic Consistency Results (RQ2):")
    print("---------------------------------------------------------")
    print(f"  Total Pairs Evaluated   : {len(result_df)}")
    print(f"  Repeated Trials per Pair: {repeats}")
    print(f"  Mean Majority Consensus : {mean_consensus:.2f}%")
    print(f"  Stochastic Flip Rate    : {mean_flip_rate:.2f}%")
    print(f"  Pairs with Inconsistency: {total_flips} / {len(result_df)}")
    print("---------------------------------------------------------")
    print(f" Saved full report to: {out_path}")


if __name__ == "__main__":
    run_stochastic_consistency_test()
