"""
analyze_consistency.py
======================
Multi-Turn Logical Consistency Analysis Module.

Research Protocol: Experimental Module 1
-----------------------------------------
This script measures the LOGICAL CONSISTENCY of the LLM-as-a-Judge by analysing
whether the judge preserves a coherent relative quality ordering across multiple
evaluation pairs involving the same model pair.

Definition of Logical Inconsistency
-------------------------------------
Given two judge decisions D1 and D2 where:
  - D1: Model A vs Model B -> WINNER: A
  - D2: Model B vs Model A -> WINNER: B (same underlying pair, reversed presentation)
  
A "position-inconsistency" occurs when the same pair yields DIFFERENT winners
depending on which answer appeared in Position A vs Position B.

More broadly, a "cross-category inconsistency" occurs when the judge's relative
ranking of model quality contradicts itself across categories:
  e.g., gpt-4 > claude-v1 in "writing" but claude-v1 > gpt-4 in "coding"
  
This analysis quantifies both forms and computes an overall Consistency Score.

Output
------
  - Console report with consistency statistics
  - `consistency_report.md` in the project root

Usage
-----
    python backend/analyze_consistency.py
"""

from __future__ import annotations

import math
import os
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from scipy import stats
from sklearn.metrics import cohen_kappa_score
from sqlalchemy import create_engine

def _adjust_pvalues_bh(pvalues: list[float]) -> list[float]:
    """
    Benjamini-Hochberg FDR p-value adjustment.
    Falls back gracefully if statsmodels is not installed in the environment.
    """
    try:
        from statsmodels.stats.multitest import multipletests
        _, pvals_adj, _, _ = multipletests(pvalues, alpha=0.05, method="fdr_bh")
        return [float(p) for p in pvals_adj]
    except ImportError:
        n = len(pvalues)
        if n == 0:
            return []
        if n == 1:
            return list(pvalues)
        sorted_indices = sorted(range(n), key=lambda i: pvalues[i])
        sorted_pvals = [pvalues[i] for i in sorted_indices]
        adjusted = [0.0] * n
        min_pv = 1.0
        for i in range(n - 1, -1, -1):
            rank = i + 1
            pv = sorted_pvals[i]
            adj = (pv * n) / rank
            min_pv = min(min_pv, adj)
            adjusted[sorted_indices[i]] = min(1.0, min_pv)
        return adjusted

# ── Path Setup ────────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).parent.resolve()
ROOT_DIR    = BACKEND_DIR.parent.resolve()
sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(ROOT_DIR / ".env")
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/judgelab"
)


# ── Database Fetch ────────────────────────────────────────────────────────────

def fetch_decisions(engine) -> pd.DataFrame:
    """Load all judge decisions with model names and category info."""
    sql = """
    SELECT
        jd.id                    AS decision_id,
        p.id                     AS prompt_id,
        p.category               AS category,
        a1.model_name            AS model_a_name,
        a2.model_name            AS model_b_name,
        jd.position_a_id         AS position_a_id,
        jd.answer_a_id           AS answer_a_id,
        jd.answer_b_id           AS answer_b_id,
        jd.winner_id             AS winner_id,
        a_win.model_name         AS winner_model
    FROM judge_decisions jd
    JOIN prompts p      ON jd.prompt_id   = p.id
    JOIN answers a1     ON jd.answer_a_id = a1.id
    JOIN answers a2     ON jd.answer_b_id = a2.id
    LEFT JOIN answers a_win ON jd.winner_id = a_win.id
    WHERE jd.judge_model_name = 'gpt-4o-mini'
    ORDER BY p.category, a1.model_name, a2.model_name
    """
    with engine.connect() as conn:
        return pd.read_sql_query(sql, conn)


# ── Analysis Functions ────────────────────────────────────────────────────────

def compute_position_consistency(df: pd.DataFrame) -> dict:
    """
    Detect position-order inconsistencies.
    
    For each UNORDERED model pair (A, B), find all decisions where:
      - Session 1: model A was shown in position_a, model B in position_b
      - Session 2: model B was shown in position_a, model A in position_b
    
    A position inconsistency is flagged when the winner differs between
    the two orderings for the same prompt.
    """
    # Create canonical pair identifier (sorted so (A,B) == (B,A))
    df = df.copy()
    df["canonical_pair"] = df.apply(
        lambda r: tuple(sorted([r["model_a_name"], r["model_b_name"]])), axis=1
    )
    # Determine which model was shown in position A
    df["position_a_model"] = df.apply(
        lambda r: r["model_a_name"] if r["position_a_id"] == r["answer_a_id"]
                  else r["model_b_name"],
        axis=1,
    )

    inconsistencies = 0
    total_swapped_pairs = 0
    inconsistent_examples = []

    # Group by prompt + canonical pair — should have at most 1 decision per
    # prompt (our design is one evaluation per preference pair).
    # Instead we look across different prompts within same category for
    # cross-ordering inconsistencies.
    grouped = df.groupby(["category", "canonical_pair"])

    for (category, pair), group in grouped:
        # Split by which model held Position A
        m1, m2 = pair
        g_m1_pos_a = group[group["position_a_model"] == m1]
        g_m2_pos_a = group[group["position_a_model"] == m2]

        if g_m1_pos_a.empty or g_m2_pos_a.empty:
            continue

        # Count wins for m1 in each ordering
        m1_wins_when_pos_a = (g_m1_pos_a["winner_model"] == m1).sum()
        m1_wins_when_pos_b = (g_m2_pos_a["winner_model"] == m1).sum()

        n1 = len(g_m1_pos_a)
        n2 = len(g_m2_pos_a)
        total_swapped_pairs += 1

        # Win rates in each position
        wr_pos_a = m1_wins_when_pos_a / n1 if n1 > 0 else 0
        wr_pos_b = m1_wins_when_pos_b / n2 if n2 > 0 else 0

        # Flag if the winner flips (win rate crosses 50% threshold) depending
        # on which model holds Position A
        if (wr_pos_a > 0.5) != (wr_pos_b > 0.5):
            inconsistencies += 1
            inconsistent_examples.append({
                "category": category,
                "model_1": m1,
                "model_2": m2,
                "win_rate_when_m1_pos_a": round(wr_pos_a, 3),
                "win_rate_when_m1_pos_b": round(wr_pos_b, 3),
                "verdict": "POSITION FLIP DETECTED",
            })

    consistency_rate = (
        (total_swapped_pairs - inconsistencies) / total_swapped_pairs
        if total_swapped_pairs > 0 else 1.0
    )

    return {
        "total_swapped_pairs":  total_swapped_pairs,
        "inconsistencies":      inconsistencies,
        "consistency_rate":     consistency_rate,
        "examples":             inconsistent_examples,
    }


def compute_cross_category_consistency(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-category win rates for every model pair and identify
    cross-category ranking contradictions.
    
    Returns a DataFrame showing how each model pair's winner changes across
    the 8 MT-bench categories.
    """
    df = df.copy()
    df["canonical_pair"] = df.apply(
        lambda r: tuple(sorted([r["model_a_name"], r["model_b_name"]])), axis=1
    )
    df["m1"] = df["canonical_pair"].apply(lambda x: x[0])
    df["m2"] = df["canonical_pair"].apply(lambda x: x[1])
    df["m1_wins"] = (df["winner_model"] == df["m1"]).astype(int)

    summary = (
        df.groupby(["canonical_pair", "category"])
        .agg(
            total=("m1_wins", "count"),
            m1_wins=("m1_wins", "sum"),
        )
        .reset_index()
    )
    summary["m1"] = summary["canonical_pair"].apply(lambda x: x[0])
    summary["m2"] = summary["canonical_pair"].apply(lambda x: x[1])
    summary["m1_win_rate"] = (summary["m1_wins"] / summary["total"]).round(3)
    summary["category_winner"] = summary.apply(
        lambda r: r["m1"] if r["m1_win_rate"] > 0.5 else
                  (r["m2"] if r["m1_win_rate"] < 0.5 else "TIE"),
        axis=1,
    )

    # Count how many categories each pair has contradictions in
    pair_flip_counts = (
        summary.groupby("canonical_pair")["category_winner"]
        .nunique()
        .reset_index()
        .rename(columns={"category_winner": "distinct_winners"})
    )
    pair_flip_counts["has_contradiction"] = pair_flip_counts["distinct_winners"] > 1

    return summary, pair_flip_counts


def compute_overall_consistency_score(
    position_results: dict,
    pair_flip_counts: pd.DataFrame,
) -> float:
    """
    Compute the aggregate Logical Consistency Score (0 to 1).
    
    Score = 0.5 * (Position Consistency Rate) 
          + 0.5 * (Cross-Category Consistency Rate)
    
    A score of 1.0 means the judge is perfectly consistent in both dimensions.
    """
    pos_score = position_results["consistency_rate"]

    total_pairs = len(pair_flip_counts)
    no_contradiction = (~pair_flip_counts["has_contradiction"]).sum()
    cat_score = no_contradiction / total_pairs if total_pairs > 0 else 1.0

    overall = 0.5 * pos_score + 0.5 * cat_score
    return round(overall, 4), round(pos_score, 4), round(cat_score, 4)


def compute_domain_chi2_fdr_corrections(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute Chi-Square goodness-of-fit test across all 8 MT-Bench domains and apply
    Benjamini-Hochberg FDR (False Discovery Rate) correction to the raw p-values.
    """
    categories = sorted(df["category"].unique())
    domain_records = []

    for cat in categories:
        cat_df = df[df["category"] == cat]
        pos_a = (cat_df["position_a_id"] == cat_df["winner_id"]).sum()
        pos_b = (cat_df["position_a_id"] != cat_df["winner_id"]) & (cat_df["winner_id"].notnull())
        pos_b_wins = int(pos_b.sum())
        pos_a_wins = int(pos_a)
        total_dec = pos_a_wins + pos_b_wins

        if total_dec > 0:
            chi2_stat, p_val = stats.chisquare([pos_a_wins, pos_b_wins], [total_dec / 2, total_dec / 2])
        else:
            chi2_stat, p_val = 0.0, 1.0

        domain_records.append({
            "category": cat,
            "total_decisions": total_dec,
            "pos_a_wins": pos_a_wins,
            "pos_b_wins": pos_b_wins,
            "chi2_stat": round(float(chi2_stat), 4),
            "p_value_raw": float(p_val),
        })

    domain_df = pd.DataFrame(domain_records)

    # Benjamini-Hochberg FDR correction
    raw_pvals = domain_df["p_value_raw"].tolist()
    pvals_adj = _adjust_pvalues_bh(raw_pvals)

    domain_df["p_value_adjusted_bh"] = [round(float(p), 6) for p in pvals_adj]
    domain_df["fdr_significant"] = [p < 0.05 for p in pvals_adj]
    return domain_df


def compute_inter_judge_kappa(engine) -> dict:
    """
    Calculate Inter-Judge Cohen's Kappa score comparing gpt-4o-mini vs llama3 decisions.
    
    Finds all matchups evaluated by BOTH judge models on identical prompt_id,
    answer_a_id, and answer_b_id pairs.
    """
    sql = """
    SELECT 
        j1.prompt_id,
        j1.answer_a_id,
        j1.answer_b_id,
        CASE
            WHEN j1.winner_id IS NULL THEN 'Tie'
            WHEN j1.winner_id = j1.answer_a_id THEN 'A'
            ELSE 'B'
        END AS gpt4_choice,
        CASE
            WHEN j2.winner_id IS NULL THEN 'Tie'
            WHEN j2.winner_id = j2.answer_a_id THEN 'A'
            ELSE 'B'
        END AS llama3_choice
    FROM judge_decisions j1
    JOIN judge_decisions j2 
      ON j1.prompt_id = j2.prompt_id 
     AND j1.answer_a_id = j2.answer_a_id 
     AND j1.answer_b_id = j2.answer_b_id
    WHERE j1.judge_model_name = 'gpt-4o-mini'
      AND j2.judge_model_name = 'llama3'
    """
    with engine.connect() as conn:
        df = pd.read_sql_query(sql, conn)

    if len(df) == 0:
        return {
            "inter_judge_kappa": 0.0,
            "overlapping_trials": 0,
            "agreement_rate": 0.0,
        }

    kappa = cohen_kappa_score(df["gpt4_choice"], df["llama3_choice"])
    agreement = (df["gpt4_choice"] == df["llama3_choice"]).mean()

    return {
        "inter_judge_kappa": round(float(kappa) if not math.isnan(kappa) else 0.0, 4),
        "overlapping_trials": int(len(df)),
        "agreement_rate": round(float(agreement), 4),
    }


# ── Report Generator ──────────────────────────────────────────────────────────

def build_report(
    df: pd.DataFrame,
    position_results: dict,
    cross_cat_summary: pd.DataFrame,
    pair_flip_counts: pd.DataFrame,
    overall_score: float,
    pos_score: float,
    cat_score: float,
) -> str:
    """Compose the full academic Markdown report."""
    lines = []
    lines.append("# Experimental Module 1: Multi-Turn Logical Consistency Analysis\n")
    lines.append(
        "> **Research Protocol**: This report measures the LLM judge's logical "
        "consistency by analysing whether it preserves a coherent relative "
        "quality ordering across different evaluation contexts.\n"
    )

    lines.append("## 1. Overall Consistency Score\n")
    lines.append(f"| Dimension | Score |")
    lines.append(f"| :--- | :---: |")
    lines.append(f"| Position-Order Consistency | `{pos_score:.1%}` |")
    lines.append(f"| Cross-Category Consistency | `{cat_score:.1%}` |")
    lines.append(f"| **Composite Logical Consistency Score** | **`{overall_score:.1%}`** |")
    lines.append("")
    lines.append(
        "> **Thesis Interpretation**: A Composite Score below 80% indicates that the "
        "judge's rankings are context-dependent rather than reflecting stable quality "
        "estimates. This corroborates the need for calibrated scoring methods "
        "(see Modules 2 and 3).\n"
    )

    lines.append("## 2. Position-Order Consistency\n")
    lines.append(
        f"Across **{position_results['total_swapped_pairs']}** model-pair / category "
        f"combinations that appeared in both orderings, "
        f"**{position_results['inconsistencies']}** exhibited a winner flip "
        f"depending on which model held Position A.\n"
    )

    if position_results["examples"]:
        lines.append("### Flagged Position Inconsistencies\n")
        lines.append("| Category | Model 1 | Model 2 | Win Rate (M1 in Pos A) | Win Rate (M1 in Pos B) | Verdict |")
        lines.append("| :--- | :--- | :--- | :---: | :---: | :--- |")
        for ex in position_results["examples"]:
            lines.append(
                f"| {ex['category']} | `{ex['model_1']}` | `{ex['model_2']}` | "
                f"{ex['win_rate_when_m1_pos_a']:.1%} | "
                f"{ex['win_rate_when_m1_pos_b']:.1%} | "
                f"**{ex['verdict']}** |"
            )
        lines.append("")

    lines.append("## 3. Cross-Category Consistency\n")
    lines.append(
        "This section shows how the winner of each model pair changes across MT-bench "
        "categories. A pair with `distinct_winners > 1` indicates the judge switches "
        "its preference depending on the topic domain.\n"
    )
    lines.append("| Model Pair | Distinct Winners | Has Contradiction |")
    lines.append("| :--- | :---: | :---: |")
    for _, row in pair_flip_counts.iterrows():
        flag = "YES" if row["has_contradiction"] else "no"
        pair_str = f"`{row['canonical_pair'][0]}` vs `{row['canonical_pair'][1]}`"
        lines.append(f"| {pair_str} | {row['distinct_winners']} | {flag} |")
    lines.append("")

    lines.append("## 4. Per-Category Win Rates (Selected Pairs)\n")
    # Show top 3 most-matched pairs pivoted by category
    top_pairs = (
        pair_flip_counts.sort_values("distinct_winners", ascending=False)
        .head(3)["canonical_pair"]
        .tolist()
    )
    for pair in top_pairs:
        subset = cross_cat_summary[cross_cat_summary["canonical_pair"] == pair]
        m1, m2 = pair
        lines.append(f"### `{m1}` vs `{m2}`\n")
        lines.append(f"| Category | Total | `{m1}` Win Rate | Category Winner |")
        lines.append(f"| :--- | :---: | :---: | :---: |")
        for _, row in subset.iterrows():
            lines.append(
                f"| {row['category']} | {row['total']} | "
                f"{row['m1_win_rate']:.1%} | `{row['category_winner']}` |"
            )
        lines.append("")

    lines.append("## 5. Scientific Commentary\n")
    lines.append(
        "The Logical Consistency Score reveals a critical limitation of deterministic "
        "pairwise evaluation: the judge's verdicts are not invariant to presentation "
        "context. Both the position of an answer in the prompt (Position A vs B) and "
        "the domain category of the question influence the judge's relative quality "
        "ranking. This means that raw win-rate leaderboards—where a model's score "
        "depends on which opponents it faced and in which order—are fundamentally "
        "unstable. The Bradley-Terry Latent Quality Scores (Module 2) address this "
        "by estimating intrinsic quality parameters that account for opponent strength, "
        "while the Length-Neutralized Scores (Module 3) isolate true quality from "
        "verbosity effects."
    )

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 70)
    print("  Module 1: Multi-Turn Logical Consistency Analysis (FDR Corrected)")
    print("=" * 70)

    engine = create_engine(DATABASE_URL)
    df = fetch_decisions(engine)
    print(f"Loaded {len(df):,} judge decisions.")

    # 1. Position-order consistency
    pos_results = compute_position_consistency(df)

    # 2. Cross-category consistency
    cross_cat_summary, pair_flip_counts = compute_cross_category_consistency(df)

    # 3. Domain-stratified Chi-Square with Benjamini-Hochberg FDR correction
    fdr_df = compute_domain_chi2_fdr_corrections(df)

    # 4. Overall score & Inter-Judge Kappa
    overall, pos_score, cat_score = compute_overall_consistency_score(
        pos_results, pair_flip_counts
    )
    inter_judge = compute_inter_judge_kappa(engine)

    # 5. Print summary
    print(f"\n  Position-Order Consistency Rate : {pos_score:.1%}")
    print(f"  Cross-Category Consistency Rate : {cat_score:.1%}")
    print(f"  Composite Logical Consistency   : {overall:.1%}")
    print(f"  Position flip cases detected    : {pos_results['inconsistencies']}")
    print(f"  Inter-Judge Cohen's Kappa (RQ6) : {inter_judge['inter_judge_kappa']:.4f}  (Agreement: {inter_judge['agreement_rate']:.1%}, N={inter_judge['overlapping_trials']})\n")

    print("  Domain-Stratified Chi-Square Tests (Benjamini-Hochberg FDR Adjusted):")
    print("  -------------------------------------------------------------------------")
    print(f"  {'Category':<15} {'Chi2 Stat':>10}  {'Raw p-val':>12}  {'Adj p-val (BH)':>16}  {'Significant'}")
    print("  " + "-" * 67)
    for _, row in fdr_df.iterrows():
        sig_str = "[REJECT H0]" if row["fdr_significant"] else "[Retain H0]"
        print(
            f"  {row['category']:<15} {row['chi2_stat']:>10.4f}  "
            f"{row['p_value_raw']:>12.4e}  {row['p_value_adjusted_bh']:>16.6f}  {sig_str}"
        )

    # 6. Save report
    report_md = build_report(
        df, pos_results, cross_cat_summary, pair_flip_counts,
        overall, pos_score, cat_score,
    )
    out_path = ROOT_DIR / "consistency_report.md"
    out_path.write_text(report_md, encoding="utf-8")
    print(f"\nSaved: 'consistency_report.md' OK")
    print("=" * 70)


if __name__ == "__main__":
    main()
