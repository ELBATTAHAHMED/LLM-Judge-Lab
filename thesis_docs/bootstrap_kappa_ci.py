"""
===============================================================================
JudgeLab (LLM-as-a-Judge Reliability Lab)
Standalone Bootstrap Confidence Interval Generator for Cohen's Kappa (κ)
===============================================================================
Author: Ahmed El Battah (Master 2 Intelligent Processing Systems)
Usage: Run directly in Google Colab, Jupyter Notebook, or local Python CLI.
Dependencies: numpy, pandas, scikit-learn
===============================================================================
"""

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

def compute_bootstrap_kappa_ci(
    rater_a: np.ndarray,
    rater_b: np.ndarray,
    n_iterations: int = 1000,
    confidence_level: float = 0.95,
    random_seed: int = 42
) -> dict:
    """
    Computes point estimate and non-parametric Bootstrap Confidence Intervals 
    for Cohen's Kappa coefficient (κ) between two evaluators.
    
    Parameters:
    -----------
    rater_a : np.ndarray
        Array of categorical decisions from Evaluator 1 (e.g., 0=A, 1=B, 2=Tie)
    rater_b : np.ndarray
        Array of categorical decisions from Evaluator 2 (e.g., 0=A, 1=B, 2=Tie)
    n_iterations : int
        Number of bootstrap resamples (default: 1000)
    confidence_level : float
        Target confidence interval width (default: 0.95 for 95% CI)
    random_seed : int
        Random seed for exact scientific reproducibility
        
    Returns:
    --------
    dict
        Dictionary containing point estimate, CI bounds, standard error, and sample size.
    """
    np.random.seed(random_seed)
    
    # 1. Point estimate calculation
    point_kappa = cohen_kappa_score(rater_a, rater_b)
    
    n_samples = len(rater_a)
    bootstrap_kappas = []
    
    # 2. Resampling with replacement
    for _ in range(n_iterations):
        indices = np.random.choice(n_samples, size=n_samples, replace=True)
        sample_a = rater_a[indices]
        sample_b = rater_b[indices]
        
        # Calculate Kappa on resampled pair
        score = cohen_kappa_score(sample_a, sample_b)
        bootstrap_kappas.append(score)
        
    bootstrap_kappas = np.array(bootstrap_kappas)
    
    # 3. Percentile-based Confidence Interval calculation
    alpha = 1.0 - confidence_level
    lower_percentile = (alpha / 2.0) * 100
    upper_percentile = (1.0 - (alpha / 2.0)) * 100
    
    ci_lower = np.percentile(bootstrap_kappas, lower_percentile)
    ci_upper = np.percentile(bootstrap_kappas, upper_percentile)
    std_err = np.std(bootstrap_kappas)
    
    return {
        "sample_size": n_samples,
        "n_iterations": n_iterations,
        "point_kappa": point_kappa,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "std_err": std_err,
        "confidence_level": confidence_level
    }


# =============================================================================
# MAIN EXECUTION DEMO (With Synthetic Data or Local CSV Data Loading)
# =============================================================================
if __name__ == "__main__":
    print("=" * 75)
    print("  JudgeLab: Bootstrap 95% Confidence Interval Analysis for Cohen's Kappa")
    print("=" * 75)
    
    # -------------------------------------------------------------------------
    # OPTION A: Load your real JudgeLab exported dataset (Uncomment when running locally)
    # -------------------------------------------------------------------------
    # df = pd.read_csv("judgelab_leaderboard_calibrated.csv")
    # rater_human = df["human_winner"].map({"A": 0, "B": 1, "TIE": 2}).values
    # rater_ai = df["ai_winner"].map({"A": 0, "B": 1, "TIE": 2}).values
    
    # -------------------------------------------------------------------------
    # OPTION B: Generate Synthetic Mock Decisions (N=1,530 matching MT-Bench scale)
    # -------------------------------------------------------------------------
    np.random.seed(42)
    N = 1530
    
    # Simulate ground-truth human annotations (0=A, 1=B, 2=Tie)
    human_decisions = np.random.choice([0, 1, 2], size=N, p=[0.40, 0.38, 0.22])
    
    # Simulate LLM judge decisions with baseline agreement (kappa ~ 0.40)
    ai_decisions = human_decisions.copy()
    noise_mask = np.random.rand(N) > 0.65  # 35% intentional decision divergence
    ai_decisions[noise_mask] = np.random.choice([0, 1, 2], size=np.sum(noise_mask))
    
    # -------------------------------------------------------------------------
    # Run Bootstrap Resampling
    # -------------------------------------------------------------------------
    results = compute_bootstrap_kappa_ci(
        rater_a=human_decisions,
        rater_b=ai_decisions,
        n_iterations=1000,
        confidence_level=0.95
    )
    
    # -------------------------------------------------------------------------
    # Print Academic Summary
    # -------------------------------------------------------------------------
    print(f"Sample Size (N)             : {results['sample_size']} pairwise trials")
    print(f"Bootstrap Resamples         : {results['n_iterations']} iterations")
    print(f"Point Estimate (Cohen's Kappa): {results['point_kappa']:.4f}")
    print(f"95% Confidence Interval     : [{results['ci_lower']:.4f}, {results['ci_upper']:.4f}]")
    print(f"Standard Error (SE)         : {results['std_err']:.4f}")
    print("-" * 75)
    print(f"Academic Thesis Statement:")
    print(f"  \"Inter-rater agreement yielded Cohen's Kappa = {results['point_kappa']:.4f} "
          f"(95% CI: [{results['ci_lower']:.4f}, {results['ci_upper']:.4f}], N = {results['sample_size']}).\"")
    print("=" * 75)
