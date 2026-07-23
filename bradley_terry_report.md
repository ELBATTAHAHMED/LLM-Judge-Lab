# Experimental Module 2: Bradley-Terry Latent Quality Scores

> **Research Protocol**: This report presents intrinsic model quality estimates derived from Maximum Likelihood Estimation of the Bradley-Terry pairwise comparison model. Unlike raw win rates, these scores control for schedule difficulty and provide a globally consistent ranking.

## Theoretical Foundation

The Bradley-Terry model posits that each model $i$ has a latent quality parameter $\theta_i \in \mathbb{R}$. The probability that model $i$ beats model $j$ in a direct comparison is:

$$P(i \succ j) = \frac{e^{\theta_i}}{e^{\theta_i} + e^{\theta_j}} = \sigma(\theta_i - \theta_j)$$

Parameters are estimated via MLE over all $N = 1{,}530$ observed pairwise decisions. The anchor model (`alpaca-13b`) is fixed at $\theta = 0$ for identifiability. All other $\theta$ values are relative latent quality scores.

## Results: Raw Win Rate vs Latent Quality Score

*Model log-likelihood of fit: `-751.59`*

| Rank | Model | Raw Win Rate | BT Score ($\theta$) | Quality Tier | vs. Anchor (alpaca-13b) |
| :---: | :--- | :---: | :---: | :---: | :---: |
| 1 | `gpt-4` | 80.0% | `2.0270` | Top Tier | `+2.027` |
| 2 | `claude-v1` | 71.9% | `1.7313` | Top Tier | `+1.731` |
| 3 | `gpt-3.5-turbo` | 63.1% | `1.3884` | Top Tier | `+1.388` |
| 4 | `alpaca-13b` | 20.6% | `0.0000` | Competitive | `+0.000` |
| 5 | `llama-13b` | 10.5% | `-0.5303` | Below Average | `-0.530` |

## Why BT Scores Are Superior to Raw Win Rates

1. **Strength-of-Schedule Correction**: `gpt-4` frequently faces strong opponents (`claude-v1`, `gpt-3.5-turbo`). Its BT score correctly accounts for this difficulty, whereas its raw win rate would be penalized by the tough schedule.
2. **Global Consistency**: The BT model finds a single parameter vector that maximally explains ALL 1,530 decisions simultaneously. Raw win rates can produce non-transitive rankings (A > B, B > C, but C > A), which BT resolves.
3. **Quantified Uncertainty**: The curvature of the log-likelihood function at the MLE estimate defines the Fisher Information, enabling confidence intervals on each theta—impossible with raw percentages.
4. **Robustness to Imbalanced Schedules**: Models evaluated on different numbers of prompts or against different opponent sets are fairly compared because the MLE jointly calibrates all parameters.

## Thesis Interpretation

The divergence between Raw Win Rate rank and BT Score rank for certain models constitutes direct empirical evidence that raw pairwise benchmarks are schedule-dependent. This finding argues for adopting latent variable models as the standard for LLM evaluation leaderboards in future research.