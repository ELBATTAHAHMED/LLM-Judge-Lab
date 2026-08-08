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


def _get_connectable(db_bind_or_session):
    """
    Safely resolve a SQLAlchemy Engine or Connection from a Session, Engine, or Connection object.
    Ensures pd.read_sql receives a valid connectable object rather than an ORM Session.
    """
    if db_bind_or_session is None:
        raise ValueError("Database connection or session cannot be None.")
    if hasattr(db_bind_or_session, "connection"):
        return db_bind_or_session.connection()
    if hasattr(db_bind_or_session, "get_bind"):
        return db_bind_or_session.get_bind()
    return db_bind_or_session


# ── Database Fetch ────────────────────────────────────────────────────────────

def fetch_decisions(engine, judge_model_name: str = "gpt-4o-mini") -> pd.DataFrame:
    """Load all judge decisions for a specific judge model with model names and category info."""
    from sqlalchemy import text
    sql = text("""
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
    WHERE jd.judge_model_name = :judge_model_name
    ORDER BY p.category, a1.model_name, a2.model_name
    """)
    conn = _get_connectable(engine)
    if hasattr(conn, "connect"):
        with conn.connect() as actual_conn:
            return pd.read_sql_query(sql, actual_conn, params={"judge_model_name": judge_model_name})
    else:
        return pd.read_sql_query(sql, conn, params={"judge_model_name": judge_model_name})


# ── Analysis Functions ────────────────────────────────────────────────────────

def compute_position_consistency(df: pd.DataFrame) -> dict:
    """
    Detect position-order inconsistencies across evaluation records.

    Methodological Note & Protocol Distinction:
    ---------------------------------------------
    1. Baseline Cross-Prompt Distributional Analysis:
       In uncalibrated baseline datasets where each prompt is evaluated once in a single
       randomized presentation order, this function aggregates decision records by category
       and model pair to compare relative win rates when Model A occupies Position A vs Position B
       across cross-prompt distributions.

    2. Strict Same-Prompt Invariance (Dual A/B Swap Calibration):
       In contrast, Dual A/B Swap calibration (executed via `run_batch_calibration.py` and
       `call_calibrated_judge`) evaluates the EXACT SAME prompt and candidate answers in both
       orderings (Pass 1: A vs B, Pass 2: B vs A) under identical context to measure strict
       prompt-level position invariance.
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

    # Group by category and canonical pair to compare cross-prompt win rates under reversed
    # presentation orderings (Baseline Cross-Prompt Analysis), as uncalibrated single-pass
    # datasets contain one evaluation trial per prompt pair.
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

    # Count how many categories each pair has domain variance in
    pair_flip_counts = (
        summary.groupby("canonical_pair")["category_winner"]
        .nunique()
        .reset_index()
        .rename(columns={"category_winner": "distinct_winners"})
    )
    pair_flip_counts["domain_specialization_variance"] = pair_flip_counts["distinct_winners"] > 1

    return summary, pair_flip_counts


def compute_overall_consistency_score(
    position_results: dict,
    pair_flip_counts: pd.DataFrame,
) -> tuple[float, float, float]:
    """
    Compute the aggregate Logical Consistency Score (0 to 1).
    
    Logical Consistency is defined strictly by Position-Order Consistency (verdict
    invariance under position swapping).
    
    Domain Specialization Variance (distinct_winners > 1 across domains) is recorded
    as a neutral descriptive metric representing domain-specific capabilities, NOT as an
    inconsistency defect.
    
    Returns
    -------
    overall_score          : float  Position-Order Consistency Rate (0 to 1)
    position_consistency   : float  Position-Order Consistency Rate (0 to 1)
    domain_specialization  : float  Rate of model pairs with domain specialization (0 to 1)
    """
    pos_score = position_results["consistency_rate"]

    total_pairs = len(pair_flip_counts)
    specialization_count = pair_flip_counts["domain_specialization_variance"].sum()

    domain_spec_rate = specialization_count / total_pairs if total_pairs > 0 else 0.0

    # Overall Logical Consistency is defined by Position-Order Consistency
    overall = pos_score
    return round(overall, 4), round(pos_score, 4), round(domain_spec_rate, 4)


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


def compute_inter_judge_kappa(
    engine,
    model_a: str = "gpt-4o-mini",
    model_b: str = "deepseek/deepseek-chat",
) -> dict:
    """
    Calculate Inter-Judge Cohen's Kappa score comparing model_a vs model_b decisions.
    
    Finds all matchups evaluated by BOTH judge models on identical prompt_id,
    answer_a_id, and answer_b_id pairs.
    """
    from sqlalchemy import text
    sql = text("""
    SELECT 
        j1.prompt_id,
        j1.answer_a_id,
        j1.answer_b_id,
        CASE
            WHEN j1.winner_id IS NULL THEN 'Tie'
            WHEN j1.winner_id = j1.answer_a_id THEN 'A'
            ELSE 'B'
        END AS choice_a,
        CASE
            WHEN j2.winner_id IS NULL THEN 'Tie'
            WHEN j2.winner_id = j2.answer_a_id THEN 'A'
            ELSE 'B'
        END AS choice_b
    FROM judge_decisions j1
    JOIN judge_decisions j2 
      ON j1.prompt_id = j2.prompt_id 
     AND j1.answer_a_id = j2.answer_a_id 
     AND j1.answer_b_id = j2.answer_b_id
    WHERE j1.judge_model_name = :model_a
      AND j2.judge_model_name = :model_b
    """)
    conn = _get_connectable(engine)
    if hasattr(conn, "connect"):
        with conn.connect() as actual_conn:
            df = pd.read_sql_query(sql, actual_conn, params={"model_a": model_a, "model_b": model_b})
    else:
        df = pd.read_sql_query(sql, conn, params={"model_a": model_a, "model_b": model_b})

    if len(df) == 0:
        return {
            "inter_judge_kappa": 0.0,
            "overlapping_trials": 0,
            "agreement_rate": 0.0,
            "model_a": model_a,
            "model_b": model_b,
        }

    kappa = cohen_kappa_score(df["choice_a"], df["choice_b"])
    agreement = (df["choice_a"] == df["choice_b"]).mean()

    return {
        "inter_judge_kappa": round(float(kappa) if not math.isnan(kappa) else 0.0, 4),
        "overlapping_trials": int(len(df)),
        "agreement_rate": round(float(agreement), 4),
        "model_a": model_a,
        "model_b": model_b,
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
    lines.append(f"| Domain Specialization Rate (Descriptive) | `{cat_score:.1%}` |")
    lines.append(f"| **Composite Logical Consistency Score** | **`{overall_score:.1%}`** |")
    lines.append("")
    lines.append(
        "> **Thesis Interpretation**: The Composite Logical Consistency Score is defined "
        "strictly by Position-Order Consistency (verdict invariance under position swapping). "
        "Domain Specialization Rate is recorded separately as a neutral descriptive metric "
        "representing model category-specific strengths, NOT as an evaluation flaw or inconsistency.\n"
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

    lines.append("## 3. Cross-Category Domain Specialization Variance\n")
    lines.append(
        "This section evaluates how relative win rates vary across MT-Bench prompt domains. "
        "A pair with `distinct_winners > 1` demonstrates Domain Specialization Variance—where "
        "model superiority shifts depending on topic domain (e.g., Coding vs Humanities), "
        "reflecting domain-specific capabilities rather than a logical defect.\n"
    )
    lines.append("| Model Pair | Distinct Winners | Domain Specialization Variance |")
    lines.append("| :--- | :---: | :---: |")
    for _, row in pair_flip_counts.iterrows():
        flag = "YES" if row["domain_specialization_variance"] else "no"
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
        "context. The position of an answer in the prompt (Position A vs B) "
        "can influence the judge's relative quality ranking. Domain Specialization Variance, "
        "meanwhile, captures topic-specific performance differentials without penalizing "
        "the judge's logical validity."
    )

    return "\n".join(lines)


# ── Self-Preference Bias Analysis ─────────────────────────────────────────────

def _extract_model_family(model_name: str | None) -> str:
    """Extract model family prefix (e.g., gpt, llama, deepseek, claude, vicuna, etc.)."""
    if not model_name:
        return "unknown"
    name = str(model_name).lower().strip()
    if "gpt" in name or "openai" in name:
        return "gpt"
    elif "llama" in name or "meta" in name:
        return "llama"
    elif "deepseek" in name:
        return "deepseek"
    elif "claude" in name or "anthropic" in name:
        return "claude"
    elif "vicuna" in name:
        return "vicuna"
    elif "mistral" in name or "mixtral" in name:
        return "mistral"
    elif "palm" in name or "gemini" in name or "bison" in name:
        return "google"
    return name.split("/")[0].split("-")[0]


def compute_self_preference_bias(db_bind_or_session, judge_model_name: str = "gpt-4o-mini") -> dict:
    """
    Measure Self-Preference Bias (whether judge model favors answers from its own model family).
    Joins judge_decisions with answers and calculates same-family win rate vs baseline win rate.
    """
    from sqlalchemy import text
    sql = text("""
        SELECT
            jd.id                    AS decision_id,
            jd.judge_model_name      AS judge_model,
            a1.model_name            AS model_a,
            a2.model_name            AS model_b,
            jd.winner_id,
            jd.answer_a_id,
            jd.answer_b_id
        FROM judge_decisions jd
        JOIN answers a1 ON jd.answer_a_id = a1.id
        JOIN answers a2 ON jd.answer_b_id = a2.id
        WHERE jd.judge_model_name = :judge_model
    """)

    try:
        conn = _get_connectable(db_bind_or_session)
        if hasattr(conn, "connect"):
            with conn.connect() as actual_conn:
                df = pd.read_sql(sql, actual_conn, params={"judge_model": judge_model_name})
        else:
            df = pd.read_sql(sql, conn, params={"judge_model": judge_model_name})
    except Exception as exc:
        import logging
        logging.error(f"[ERROR] Failed to query decisions for self-preference bias for model '{judge_model_name}': {exc}", exc_info=True)
        raise exc

    judge_family = _extract_model_family(judge_model_name)

    if df.empty:
        return {
            "judge_model": judge_model_name,
            "judge_family": judge_family,
            "self_win_rate": None,
            "baseline_win_rate": None,
            "self_preference_ratio": None,
            "self_preference_detected": False,
            "total_self_matchups": 0,
            "total_other_matchups": 0,
            "p_value": None,
            "statistically_significant": False,
        }

    self_wins = 0
    self_matchups = 0
    other_wins = 0
    other_matchups = 0

    for _, row in df.iterrows():
        fam_a = _extract_model_family(row["model_a"])
        fam_b = _extract_model_family(row["model_b"])
        winner_id = row["winner_id"]
        a_id = row["answer_a_id"]
        b_id = row["answer_b_id"]

        is_a_self = (fam_a == judge_family)
        is_b_self = (fam_b == judge_family)

        if is_a_self and not is_b_self:
            self_matchups += 1
            if winner_id == a_id:
                self_wins += 1
        elif is_b_self and not is_a_self:
            self_matchups += 1
            if winner_id == b_id:
                self_wins += 1
        elif not is_a_self and not is_b_self:
            other_matchups += 1
            if winner_id == a_id:
                other_wins += 1

    if self_matchups == 0:
        other_win_rate = (other_wins / other_matchups) if other_matchups > 0 else None
        return {
            "judge_model": judge_model_name,
            "judge_family": judge_family,
            "self_win_rate": None,
            "baseline_win_rate": round(other_win_rate, 4) if other_win_rate is not None else None,
            "self_preference_ratio": None,
            "self_preference_detected": False,
            "total_self_matchups": 0,
            "total_other_matchups": other_matchups,
            "p_value": None,
            "statistically_significant": False,
        }

    self_win_rate = self_wins / self_matchups
    other_win_rate = (other_wins / other_matchups) if other_matchups > 0 else None
    ratio = (self_win_rate / other_win_rate) if (other_win_rate is not None and other_win_rate > 0) else None

    p_val = None
    try:
        from scipy.stats import binomtest
        # Null hypothesis baseline p0 is the judge's win rate on rival model families
        null_p = other_win_rate if (other_win_rate is not None and 0 < other_win_rate < 1) else 0.5
        res = binomtest(self_wins, self_matchups, p=null_p, alternative="greater")
        p_val = float(res.pvalue)
    except Exception:
        p_val = None

    is_significant = bool(p_val is not None and p_val < 0.05)

    return {
        "judge_model": judge_model_name,
        "judge_family": judge_family,
        "self_win_rate": round(self_win_rate, 4),
        "baseline_win_rate": round(other_win_rate, 4) if other_win_rate is not None else None,
        "self_preference_ratio": round(ratio, 4) if ratio is not None else None,
        "self_preference_detected": bool(other_win_rate is not None and self_win_rate > other_win_rate and is_significant),
        "total_self_matchups": self_matchups,
        "total_other_matchups": other_matchups,
        "p_value": round(p_val, 6) if p_val is not None else None,
        "statistically_significant": is_significant,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Analyze logical consistency metrics for LLM judge.")
    parser.add_argument("--model", default="gpt-4o-mini", help="Judge model name to analyze.")
    args = parser.parse_args()

    print("=" * 70)
    print(f"  Module 1: Multi-Turn Logical Consistency Analysis (Model: {args.model})")
    print("=" * 70)

    engine = create_engine(DATABASE_URL)
    df = fetch_decisions(engine, judge_model_name=args.model)
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
    print(f"  Domain Specialization Rate      : {cat_score:.1%}")
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
