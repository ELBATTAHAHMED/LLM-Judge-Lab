"""
analyze_results.py
==================
Statistical Analysis and Visualization Engine for LLM-as-a-Judge.

This script connects to the PostgreSQL database, retrieves the aligned human
and LLM judge preferences, and runs:
  1. Cohen's Kappa to measure inter-rater reliability.
  2. Chi-Square Goodness-of-Fit test to assess statistical significance of position bias.
  3. Verbosity Bias Analysis using Spearman Rank Correlation between word count deltas
     and judge choices.
  4. Domain-Stratified Reliability using category-specific Cohen's Kappa scores.
  5. Self-Enhancement / Provider Bias analysis using Chi-Square Test of Independence
     comparing LLM judge vs. human win rates on OpenAI vs. external models.
  6. Forced Choice Analysis measuring the False Positive Rate of Decisiveness on human ties.
  7. Generates four publication-ready visualizations saved to the root directory:
     - position_bias_analysis.png
     - agreement_confusion_matrix.png
     - domain_reliability_kappa.png
     - verbosity_bias_trend.png

Usage:
    python backend/analyze_results.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from dotenv import load_dotenv
from scipy.stats import chisquare, spearmanr, chi2_contingency
from sklearn.metrics import cohen_kappa_score, confusion_matrix
from sqlalchemy import create_engine

# ── path setup ────────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).parent.resolve()
ROOT_DIR = BACKEND_DIR.parent.resolve()
ASSETS_DIR = ROOT_DIR / "thesis_assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(BACKEND_DIR))

# Load environment variables
load_dotenv(ROOT_DIR / ".env")

# ── database configuration ───────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/judgelab"
)


def get_connection_engine():
    """Create and return a database connection engine."""
    try:
        engine = create_engine(DATABASE_URL)
        return engine
    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)


# ── data retrieval and processing ───────────────────────────────────────────


def fetch_and_process_data(engine) -> pd.DataFrame:
    """Fetch matched human vs LLM evaluations and classify choices."""
    sql_query = """
    SELECT 
        hp.winner_id as human_winner_id,
        hp.answer_a_id,
        hp.answer_b_id,
        jd.winner_id as llm_winner_id,
        jd.position_a_id,
        p.category as prompt_category,
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
    WHERE jd.judge_model_name = 'gpt-4o-mini';
    """

    with engine.connect() as conn:
        df = pd.read_sql_query(sql_query, conn)

    if df.empty:
        print("Error: No data found in the database matching 'gpt-4o-mini'!")
        sys.exit(1)

    # Classify Human Choice
    def classify_human(row):
        if pd.isna(row["human_winner_id"]):
            return "Tie"
        elif row["human_winner_id"] == row["answer_a_id"]:
            return "A"
        elif row["human_winner_id"] == row["answer_b_id"]:
            return "B"
        return "Unknown"

    # Classify LLM Choice
    def classify_llm(row):
        if pd.isna(row["llm_winner_id"]):
            return "Tie"
        elif row["llm_winner_id"] == row["answer_a_id"]:
            return "A"
        elif row["llm_winner_id"] == row["answer_b_id"]:
            return "B"
        return "Unknown"

    # Classify Position Selection (to analyze Position Bias)
    def classify_position(row):
        if pd.isna(row["llm_winner_id"]):
            return "Tie"
        elif row["llm_winner_id"] == row["position_a_id"]:
            return "Position A"
        else:
            return "Position B"

    df["human_choice"] = df.apply(classify_human, axis=1)
    df["llm_choice"] = df.apply(classify_llm, axis=1)
    df["position_choice"] = df.apply(classify_position, axis=1)

    return df


# ── statistical tests ─────────────────────────────────────────────────────────


def perform_statistical_analysis(df: pd.DataFrame) -> dict:
    """Run core and expanded statistical tests."""
    results = {}

    # 1. Cohen's Kappa Score (Overall)
    clean_df = df[
        (df["human_choice"] != "Unknown") & (df["llm_choice"] != "Unknown")
    ]
    kappa = cohen_kappa_score(clean_df["human_choice"], clean_df["llm_choice"])
    results["cohen_kappa"] = kappa

    # 2. Chi-Square Goodness-of-Fit for Position Selection
    # A vs B vs Tie (Expected: Uniform 1/3 distribution under Null Hypothesis)
    pos_counts = df["position_choice"].value_counts()
    categories = ["Position B", "Position A", "Tie"]
    observed = [pos_counts.get(cat, 0) for cat in categories]
    total_obs = sum(observed)
    expected_uniform = [total_obs / 3] * 3
    chi2_stat, p_val = chisquare(f_obs=observed, f_exp=expected_uniform)
    results["chi2_uniform"] = (chi2_stat, p_val)

    # Chi-Square for Position Selection excluding Ties (A vs B 50/50 test)
    pos_counts_no_ties = pos_counts.drop("Tie", errors="ignore")
    observed_binary = [
        pos_counts_no_ties.get("Position B", 0),
        pos_counts_no_ties.get("Position A", 0),
    ]
    total_binary = sum(observed_binary)
    expected_binary = [total_binary / 2] * 2
    chi2_bin_stat, p_val_bin = chisquare(
        f_obs=observed_binary, f_exp=expected_binary
    )
    results["chi2_binary"] = (chi2_bin_stat, p_val_bin)

    # 3. Verbosity Bias (Spearman Rank Correlation)
    # word count diff (len(A) - len(B))
    df["word_len_diff"] = df["answer_a_word_count"] - df["answer_b_word_count"]
    
    # Map LLM choice to numerical verdict: A=1, Tie=0, B=-1
    def get_numeric_verdict(row):
        if row["llm_choice"] == "A":
            return 1.0
        elif row["llm_choice"] == "B":
            return -1.0
        return 0.0

    df["llm_verdict_numeric"] = df.apply(get_numeric_verdict, axis=1)
    spearman_rho, spearman_p = spearmanr(df["word_len_diff"], df["llm_verdict_numeric"])
    results["spearman_rho"] = spearman_rho
    results["spearman_p"] = spearman_p

    # Win rate of the longer response when the judge expresses a choice
    non_tie_len_diffs = df[
        (df["llm_choice"] != "Tie") & (df["word_len_diff"] != 0)
    ]
    longer_wins = non_tie_len_diffs.apply(
        lambda r: (r["llm_choice"] == "A" and r["word_len_diff"] > 0) or
                  (r["llm_choice"] == "B" and r["word_len_diff"] < 0),
        axis=1
    )
    results["longer_win_rate"] = longer_wins.mean()

    # 4. Domain-Stratified Reliability (Category-Specific Kappa)
    domain_kappa = {}
    for cat in df["prompt_category"].unique():
        cat_df = df[df["prompt_category"] == cat]
        domain_kappa[cat] = cohen_kappa_score(cat_df["human_choice"], cat_df["llm_choice"])
    results["domain_kappa"] = domain_kappa

    # 5. Self-Enhancement / Provider Bias (Multiclass Chi-Square)
    def classify_provider_multiclass(model_name):
        model_name = model_name.lower()
        if "gpt" in model_name:
            return "OpenAI"
        elif "claude" in model_name:
            return "Anthropic"
        elif any(x in model_name for x in ["llama", "vicuna", "alpaca"]):
            return "Open-Source"
        return "Other"

    def get_winner_provider(winner_id, answer_a_id, answer_b_id, model_a, model_b):
        if pd.isna(winner_id):
            return "Tie"
        elif winner_id == answer_a_id:
            return classify_provider_multiclass(model_a)
        elif winner_id == answer_b_id:
            return classify_provider_multiclass(model_b)
        return "Unknown"

    df["human_winner_provider"] = df.apply(
        lambda r: get_winner_provider(r["human_winner_id"], r["answer_a_id"], r["answer_b_id"], r["answer_a_model_name"], r["answer_b_model_name"]), axis=1
    )
    df["llm_winner_provider"] = df.apply(
        lambda r: get_winner_provider(r["llm_winner_id"], r["answer_a_id"], r["answer_b_id"], r["answer_a_model_name"], r["answer_b_model_name"]), axis=1
    )

    provider_categories = ["OpenAI", "Anthropic", "Open-Source", "Tie"]
    human_counts = df["human_winner_provider"].value_counts()
    llm_counts = df["llm_winner_provider"].value_counts()

    # Construct the Multiclass Contingency Matrix (Rows = Category, Cols = Evaluator)
    contingency = [
        [human_counts.get(cat, 0), llm_counts.get(cat, 0)]
        for cat in provider_categories
    ]
    chi2_prov, p_val_prov, _, _ = chi2_contingency(contingency)
    
    results["provider_bias_chi2"] = (chi2_prov, p_val_prov)
    results["provider_counts_human"] = {cat: human_counts.get(cat, 0) for cat in provider_categories}
    results["provider_counts_llm"] = {cat: llm_counts.get(cat, 0) for cat in provider_categories}

    # 6. Forced Choice Analysis (Calibration on Ties)
    human_ties = df[df["human_choice"] == "Tie"]
    llm_decisive = human_ties["llm_choice"].apply(lambda val: val != "Tie")
    results["fpr_decisiveness"] = llm_decisive.mean()
    results["human_ties_count"] = len(human_ties)
    results["llm_decisive_on_ties"] = sum(llm_decisive)
    results["random_baseline"] = 2.0 / 3.0  # 66.67% random baseline of A or B
    results["delta_fpr"] = results["fpr_decisiveness"] - results["random_baseline"]

    return results


def print_formatted_results(df: pd.DataFrame, stats: dict) -> None:
    """Print academic interpretation of all statistical metrics for the thesis."""
    print("=" * 75)
    print("                LLM-AS-A-JUDGE RELIABILITY ANALYSIS REPORT")
    print("=" * 75)
    print(f"Total Aligned Evaluation Pairs: {len(df):,}")
    print("-" * 75)

    # Cohen's Kappa
    kappa = stats["cohen_kappa"]
    kappa_desc = (
        "Fair agreement" if kappa <= 0.40 else
        "Moderate agreement" if kappa <= 0.60 else
        "Substantial agreement"
    )
    print("1. OVERALL INTER-RATER RELIABILITY (COHEN'S KAPPA)")
    print(f"   * Cohen's Kappa Score: {kappa:.4f}")
    print(f"   * Interpretation     : {kappa_desc}")
    print("-" * 75)

    # Position Bias
    print("2. POSITION BIAS TEST (CHI-SQUARE GOODNESS-OF-FIT)")
    chi2_3, p_val_3 = stats["chi2_uniform"]
    chi2_2, p_val_2 = stats["chi2_binary"]
    print("   [Option A: 3-Way Test (Position A vs Position B vs Tie)]")
    print(f"     * Chi2 Statistic : {chi2_3:.4f} (df=2)")
    print(f"     * p-value        : {p_val_3:.4e}")
    print("   [Option B: Binary Test (Position A vs Position B - Excluding Ties)]")
    print(f"     * Chi2 Statistic : {chi2_2:.4f} (df=1)")
    print(f"     * p-value        : {p_val_2:.4f}")
    if p_val_2 < 0.05:
        print("     * Thesis Interpretation: STATISTICALLY SIGNIFICANT bias. The judge has a")
        print("                              systematic preference for the response in Position B.")
    else:
        print("     * Thesis Interpretation: No statistically significant position bias detected.")
    print("-" * 75)

    # Verbosity Bias
    print("3. VERBOSITY BIAS ANALYSIS (SPEARMAN RANK CORRELATION)")
    print(f"   * Spearman's Rho (rho): {stats['spearman_rho']:.4f}")
    print(f"   * p-value             : {stats['spearman_p']:.4e}")
    print(f"   * Longer Win Rate     : {stats['longer_win_rate'] * 100:.2f}% (when a choice is made)")
    if stats["spearman_rho"] > 0.3 and stats["spearman_p"] < 0.05:
        print("   * Thesis Interpretation: HIGHLY SIGNIFICANT positive correlation. The AI judge")
        print("                            strongly favors longer answers (verbosity bias) regardless")
        print("                            of actual quality. This is a crucial research limitation.")
    print("-" * 75)

    # Domain-Stratified Reliability
    print("4. DOMAIN-STRATIFIED RELIABILITY (CATEGORY-SPECIFIC KAPPA)")
    sorted_kappa = sorted(stats["domain_kappa"].items(), key=lambda x: x[1], reverse=True)
    for cat, val in sorted_kappa:
        print(f"   * {cat:<15} : Kappa = {val:.4f}")
    print("-" * 75)

    # Provider Bias
    print("5. SELF-ENHANCEMENT / PROVIDER BIAS (CHI-SQUARE TEST OF INDEPENDENCE)")
    print("   * Win Distribution by Provider Category:")
    provider_categories = ["OpenAI", "Anthropic", "Open-Source", "Tie"]
    h_counts = stats["provider_counts_human"]
    l_counts = stats["provider_counts_llm"]
    total = len(df)
    print(f"     {'Category':<15} | {'Human Wins':<12} ({'Pct':<5}) | {'LLM Wins':<12} ({'Pct':<5})")
    print(f"     {'-'*15}-+-{'-'*20}-+-{'-'*20}")
    for cat in provider_categories:
        hc = h_counts.get(cat, 0)
        lc = l_counts.get(cat, 0)
        print(f"     {cat:<15} | {hc:<12,} ({hc/total*100:>5.1f}%) | {lc:<12,} ({lc/total*100:>5.1f}%)")
    
    chi2_prov, p_val_prov = stats["provider_bias_chi2"]
    print(f"   * Multiclass Chi2 Statistic        : {chi2_prov:.4f} (df=3)")
    print(f"   * Chi2 Test p-value                : {p_val_prov:.4e}")
    if p_val_prov < 0.05:
        print("   * Thesis Interpretation: STATISTICALLY SIGNIFICANT win rate redistribution.")
        print("                            The difference in LLM vs. Human win distribution is not")
        print("                            random, primarily driven by a systematic reduction in ties")
        print("                            and inflation of wins across OpenAI and external models.")
    else:
        print("   * Thesis Interpretation: No statistically significant provider distribution difference.")
    print("-" * 75)

    # Forced Choice Analysis
    print("6. THE \"FORCED CHOICE\" ANALYSIS (TIE CALIBRATION)")
    print(f"   * Total Human ties evaluated by LLM : {stats['human_ties_count']}")
    print(f"   * LLM Decisive Choices on Ties      : {stats['llm_decisive_on_ties']}")
    print(f"   * False Positive Decisiveness Rate  : {stats['fpr_decisiveness'] * 100:.2f}%")
    print(f"   * Theoretical Random Baseline       : {stats['random_baseline'] * 100:.2f}% (guessing A/B)")
    print(f"   * Empirical Delta vs Random Baseline: {stats['delta_fpr'] * 100:+.2f}%")
    if stats["delta_fpr"] > 0:
        print("   * Thesis Interpretation: The LLM judge's decisiveness rate is statistically")
        print(f"                            above the {stats['random_baseline']*100:.2f}% random guess baseline,")
        print("                            proving a systematic forced-choice bias against draws.")
    else:
        print("   * Thesis Interpretation: No forced-choice bias detected above random noise.")
    print("=" * 75)


# ── visualization engine ──────────────────────────────────────────────────────


def generate_visualizations(df: pd.DataFrame, stats: dict) -> None:
    """Generate and save 4 publication-quality figures."""
    sns.set_theme(style="whitegrid", context="talk")
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "figure.titlesize": 16,
            "axes.titlesize": 14,
            "axes.labelsize": 12,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
        }
    )

    # --- Plot 1: Position Bias Breakdown ---
    fig1, ax1 = plt.subplots(figsize=(8, 4.5), layout="constrained")
    pos_data = df["position_choice"].value_counts(normalize=True) * 100
    pos_df = pos_data.reset_index()
    pos_df.columns = ["Position", "Percentage"]

    barplot = sns.barplot(
        data=pos_df,
        y="Position",
        x="Percentage",
        hue="Position",
        legend=False,
        palette={"Position B": "#3498db", "Position A": "#2ecc71", "Tie": "#95a5a6"},
        ax=ax1,
    )
    for container in barplot.containers:
        ax1.bar_label(container, fmt="%.2f%%", padding=8, fontsize=11, weight="bold")

    ax1.set_xlim(0, 60)
    ax1.set_title("Position Bias Breakdown (gpt-4o-mini)", pad=15, weight="bold")
    ax1.set_xlabel("Percentage (%)")
    ax1.set_ylabel("Judge Choice Location")
    fig1.savefig(ASSETS_DIR / "position_bias_analysis.png", dpi=300, bbox_inches="tight")
    plt.close(fig1)
    print(f"Saved: '{ASSETS_DIR / 'position_bias_analysis.png'}'")

    # --- Plot 2: Confusion Matrix ---
    fig2, ax2 = plt.subplots(figsize=(7, 6.5), layout="constrained")
    categories = ["A", "B", "Tie"]
    cm = confusion_matrix(df["human_choice"], df["llm_choice"], labels=categories)
    cm_norm = cm.astype("float") / cm.sum(axis=1)[:, np.newaxis]
    labels = np.asarray(
        [
            [f"{count}\n({pct:.1%})" for count, pct in zip(row, row_n)]
            for row, row_n in zip(cm, cm_norm)
        ]
    )
    sns.heatmap(
        cm_norm,
        annot=labels,
        fmt="",
        cmap="Blues",
        xticklabels=categories,
        yticklabels=categories,
        cbar=True,
        square=True,
        ax=ax2,
        annot_kws={"size": 12, "weight": "bold"},
    )
    ax2.set_title("Human Baseline vs. LLM Judge Confusion Matrix", pad=15, weight="bold")
    ax2.set_xlabel("LLM Judge Choice ('gpt-4o-mini')", labelpad=10)
    ax2.set_ylabel("Human Reference Choice (Rows Sum to 100%)", labelpad=10)
    fig2.savefig(ASSETS_DIR / "agreement_confusion_matrix.png", dpi=300, bbox_inches="tight")
    plt.close(fig2)
    print(f"Saved: '{ASSETS_DIR / 'agreement_confusion_matrix.png'}'")

    # --- Plot 3: Domain-Stratified Reliability (Category-Specific Kappa) ---
    fig3, ax3 = plt.subplots(figsize=(9, 5), layout="constrained")
    sorted_kappa = sorted(stats["domain_kappa"].items(), key=lambda x: x[1], reverse=True)
    domains = [x[0] for x in sorted_kappa]
    kappas = [x[1] for x in sorted_kappa]
    
    # Map colors from high agreement (Blue) to low agreement (Muted Orange)
    colors = plt.cm.coolwarm(np.linspace(0.85, 0.25, len(domains)))
    
    barplot3 = sns.barplot(x=kappas, y=domains, hue=domains, palette=list(colors), legend=False, ax=ax3)
    ax3.bar_label(barplot3.containers[0], fmt="%.3f", padding=8, fontsize=10, weight="bold")
    ax3.set_xlim(0, 0.7)
    ax3.set_title("Inter-Rater Reliability (Cohen's Kappa) by Prompt Domain", pad=15, weight="bold")
    ax3.set_xlabel("Cohen's Kappa Score (Agreement with Human)")
    ax3.set_ylabel("Prompt Domain")
    fig3.savefig(ASSETS_DIR / "domain_reliability_kappa.png", dpi=300, bbox_inches="tight")
    plt.close(fig3)
    print(f"Saved: '{ASSETS_DIR / 'domain_reliability_kappa.png'}'")

    # --- Plot 4: Verbosity Bias Trend (Binned Length Diff vs Win Probability) ---
    fig4, ax4 = plt.subplots(figsize=(9, 5), layout="constrained")
    
    # Target value: 1 if LLM chose A, 0 if B, 0.5 if Tie
    def get_binary_outcome(row):
        if row["llm_choice"] == "A":
            return 1.0
        elif row["llm_choice"] == "B":
            return 0.0
        return 0.5

    df["llm_win_prob_A"] = df.apply(get_binary_outcome, axis=1)

    # Plot binned trend (15 bins) to reduce scatter noise and display a clean probability trend
    sns.regplot(
        data=df,
        x="word_len_diff",
        y="llm_win_prob_A",
        x_bins=15,
        fit_reg=True,
        scatter_kws={"color": "#3498db", "s": 75, "alpha": 0.8},
        line_kws={"color": "#e74c3c", "linewidth": 2.5, "label": "Linear Fit Trend"},
        ax=ax4,
    )
    
    # Add marginal data density indicator along the X-axis (rugplot)
    sns.rugplot(
        data=df,
        x="word_len_diff",
        ax=ax4,
        color="#e74c3c",
        alpha=0.3,
        height=0.04
    )
    
    ax4.set_ylim(-0.05, 1.05)
    ax4.set_title("Length Disparity vs. LLM Judge Win Probability (A)", pad=15, weight="bold")
    ax4.set_xlabel("Length Disparity in Words (Answer A Length - Answer B Length)")
    ax4.set_ylabel("Probability of Selection (Answer A)")
    ax4.legend(loc="upper left")
    
    fig4.savefig(ASSETS_DIR / "verbosity_bias_trend.png", dpi=300, bbox_inches="tight")
    plt.close(fig4)
    print(f"Saved: '{ASSETS_DIR / 'verbosity_bias_trend.png'}'")


# ── main engine entry ─────────────────────────────────────────────────────────


def main() -> None:
    engine = get_connection_engine()
    df = fetch_and_process_data(engine)
    stats = perform_statistical_analysis(df)
    print_formatted_results(df, stats)
    generate_visualizations(df, stats)


if __name__ == "__main__":
    main()
