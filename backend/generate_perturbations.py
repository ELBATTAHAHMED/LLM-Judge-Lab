"""
generate_perturbations.py
=========================
Controlled Synthetic Perturbation & Counterfactual Bias Isolation Engine.

Rigorously isolates verbosity bias and format bias by evaluating an LLM judge
on semantically identical answer pairs modified with:
  1. Verbosity (Length) Padding (+30-50% word count expansion)
  2. Structural Markdown Syntax Injection (Headers, Bold, Bullet points)

Outputs:
  - `qualitative_data/perturbation_test_results.csv`
  - Console summary breakdown table
"""

from __future__ import annotations

import os
import sys
import time
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import text
from openai import OpenAI

# Path Setup
BACKEND_DIR = Path(__file__).parent.resolve()
ROOT_DIR = BACKEND_DIR.parent.resolve()
sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(ROOT_DIR / ".env")
QUALITATIVE_DIR = ROOT_DIR / "qualitative_data"

from database import engine
from judge_engine import call_judge


def load_base_pairs(sample_size: int = 20, seed: int = 42) -> pd.DataFrame:
    """Load a deterministic subset of clean evaluation pairs."""
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT hp.id as pair_id, p.id as prompt_id, p.text as question,
                       a1.text as answer_a, a2.text as answer_b
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
        print(f"Database notice: {exc}. Falling back to CSV dataset.")

    csv_path = QUALITATIVE_DIR / "qualitative_baseline_alignment.csv"
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        return df.sample(n=min(sample_size, len(df)), random_state=seed).reset_index(drop=True)

    raise FileNotFoundError("Could not load evaluation pairs.")


def apply_verbosity_padding(text_content: str) -> str:
    """Append semantically neutral, repetitive padding to inflate word count by 30-50%."""
    padding = (
        "\n\nIn summary, to reiterate our prior points and provide additional context on the matter, "
        "this thoroughly concludes the explanation. Furthermore, all presented concepts have been "
        "carefully synthesized to ensure maximum clarity, structure, and completeness for the reader."
    )
    return text_content + padding


def apply_markdown_injection(text_content: str) -> str:
    """Inject Markdown headers, bolding, and bullet syntax into plain text."""
    lines = [line.strip() for line in text_content.split("\n") if line.strip()]
    if not lines:
        return "### **Key Synthesis**\n- " + text_content

    formatted_lines = ["### **Core Summary & Key Insights**"]
    for idx, line in enumerate(lines):
        if idx == 0:
            formatted_lines.append(f"**Primary Point:** {line}")
        elif idx % 2 == 1:
            formatted_lines.append(f"- **Key Detail:** {line}")
        else:
            formatted_lines.append(f"- {line}")

    return "\n\n".join(formatted_lines)


def run_controlled_perturbation_experiments(
    sample_size: int = 20,
    model_name: str = "gpt-4o-mini",
    temperature: float = 0.0,
    max_workers: int = 10,
):
    print("=========================================================")
    print(" Starting Controlled Synthetic Perturbation Engine")
    print(f" Sample Base Pairs: {sample_size} | Model: {model_name} | T = {temperature}")
    print(f" Parallel Workers: {max_workers}")
    print("=========================================================")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is missing in .env.")

    client = OpenAI(api_key=api_key)
    df_pairs = load_base_pairs(sample_size=sample_size, seed=42)

    eval_tasks = []

    for idx, row in df_pairs.iterrows():
        prompt_id = int(row.get("prompt_id", idx + 1))
        question = str(row.get("question", row.get("reasoning_text", "Evaluate responses")))
        answer_orig = str(row.get("answer_a", "Original response text"))

        # Task 1: Verbosity Padding Counterfactual (Original vs Padded Original)
        padded_answer = apply_verbosity_padding(answer_orig)
        delta_words_v = len(padded_answer.split()) - len(answer_orig.split())

        eval_tasks.append({
            "prompt_id": prompt_id,
            "perturbation_type": "verbosity_padding",
            "question": question,
            "answer_a": answer_orig,       # Position A: Original
            "answer_b": padded_answer,     # Position B: Padded
            "expected_unbiased_winner": "TIE",
            "perturbed_target_position": "B",
            "delta_word_count": delta_words_v,
        })

        # Task 2: Markdown Injection Counterfactual (Plain vs Markdown Formatted)
        markdown_answer = apply_markdown_injection(answer_orig)
        delta_words_m = len(markdown_answer.split()) - len(answer_orig.split())

        eval_tasks.append({
            "prompt_id": prompt_id,
            "perturbation_type": "markdown_injection",
            "question": question,
            "answer_a": answer_orig,        # Position A: Original (Plain)
            "answer_b": markdown_answer,    # Position B: Markdown Formatted
            "expected_unbiased_winner": "TIE",
            "perturbed_target_position": "B",
            "delta_word_count": delta_words_m,
        })

    print(f"Generated {len(eval_tasks)} counterfactual evaluation tasks. Dispatching to OpenAI API...")

    def execute_counterfactual(task):
        for attempt in range(3):
            try:
                res = call_judge(
                    client=client,
                    question=task["question"],
                    answer_a=task["answer_a"],
                    answer_b=task["answer_b"],
                    model_name=model_name,
                    temperature=temperature,
                )
                winner = res.verdict  # "A", "B", "TIE", "UNKNOWN"
                verdict_flipped = (winner == task["perturbed_target_position"])

                return {
                    "prompt_id": task["prompt_id"],
                    "perturbation_type": task["perturbation_type"],
                    "original_winner": "A (Original)",
                    "perturbed_winner": f"{winner} (Perturbed Chosen)" if verdict_flipped else f"{winner} (Unflipped)",
                    "verdict_flipped": verdict_flipped,
                    "delta_word_count": task["delta_word_count"],
                    "judge_verdict_raw": winner,
                }
            except Exception as exc:
                print(f"Task warning ({task['perturbation_type']}): {exc}. Retrying in 2s...")
                time.sleep(2)

        return {
            "prompt_id": task["prompt_id"],
            "perturbation_type": task["perturbation_type"],
            "original_winner": "A (Original)",
            "perturbed_winner": "UNKNOWN",
            "verdict_flipped": False,
            "delta_word_count": task["delta_word_count"],
            "judge_verdict_raw": "UNKNOWN",
        }

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(execute_counterfactual, task) for task in eval_tasks]
        for future in as_completed(futures):
            results.append(future.result())

    results_df = pd.DataFrame(results).sort_values(by=["perturbation_type", "prompt_id"])

    # Export to CSV
    out_csv_path = QUALITATIVE_DIR / "perturbation_test_results.csv"
    QUALITATIVE_DIR.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(out_csv_path, index=False)

    # Console Summary Table
    print("\n=========================================================")
    print(" Controlled Synthetic Perturbation Results Summary")
    print("=========================================================")
    for p_type, group in results_df.groupby("perturbation_type"):
        total = len(group)
        flips = group["verdict_flipped"].sum()
        flip_rate = (flips / total) * 100 if total > 0 else 0.0
        avg_delta_len = group["delta_word_count"].mean()

        print(f"\n[Perturbation Category: {p_type.upper()}]")
        print(f"  Total Counterfactual Pairs : {total}")
        print(f"  Synthetic Verdict Flips    : {flips} / {total}")
        print(f"  Perturbation Flip Rate     : {flip_rate:.2f}%")
        print(f"  Mean Delta Word Count      : +{avg_delta_len:.1f} words")

    print("---------------------------------------------------------")
    print(f" Saved structured perturbation dataset to: {out_csv_path}")


if __name__ == "__main__":
    run_controlled_perturbation_experiments()
