# Experimental Module 3: Residual-Based Length Neutralization

> **Research Protocol**: This report decomposes judge win probabilities into a length-explained component and a Pure Quality residual, enabling verbosity-independent model ranking.

## 1. Length-Bias Regression Results

The linear regression `Win_A ~ alpha + beta * (WC_A - WC_B)` was fit on all **6** model decisions.

| Parameter | Value | Interpretation |
| :--- | :---: | :--- |
| Intercept (α) | `0.4970` | Baseline win prob at equal word counts |
| Length-Bias Coefficient (β) | `0.000679` | Win prob change per extra word in Answer A |
| Standard Error of β | `0.000059` | Precision of the bias estimate |
| R² | `0.0544` | Variance explained by length alone |
| P-value | `0.0000` | **Statistically significant** (p < 0.05) — length is a genuine predictor of winning. |

> ⚠️ **Verbosity Bias Confirmed**: The positive β coefficient means the judge is measurably more likely to declare a winner for the LONGER answer. Each additional 100 words in Answer A increases its win probability by approximately **0.07 percentage points**.

## 2. Raw Win Rate vs Neutralized Quality Score

The Neutralized Score is the model's **mean residual** — how much it over- or under-performs relative to the length-baseline prediction. A positive score indicates genuine quality that exceeds length expectations.

| Neutralized Rank | Model | Total Games | Raw Win Rate | Raw Rank | Neutralized Score | Rank Change |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| 1 | `gpt-4` | 724 | 68.0% | #1 | `+0.22997` | — |
| 2 | `claude-v1` | 726 | 62.5% | #2 | `+0.18161` | — |
| 3 | `gpt-3.5-turbo` | 925 | 52.4% | #3 | `+0.10038` | — |
| 4 | `vicuna-13b` | 741 | 40.9% | #4 | `-0.03270` | — |
| 5 | `alpaca-13b` | 696 | 16.2% | #5 | `-0.18685` | — |
| 6 | `llama-13b` | 730 | 10.5% | #6 | `-0.32455` | — |

## 3. Scientific Commentary

**Interpretation of β**: The positive and statistically significant slope (β = 0.000679) confirms that the `gpt-4o-mini` judge exhibits systematic verbosity bias. This is not a random artifact—it is a systematic, reproducible distortion in the evaluation function.

**Rank Changes**: Models that rise in the Neutralized ranking (positive rank change) are those whose apparent raw win rate was SUPPRESSED because they tend to produce concise answers. They are 'undervalued' by the raw benchmark. Conversely, models that fall in the Neutralized ranking were inflated by verbosity effects.

**Thesis Claim**: The residual-based neutralized score provides a purer estimate of model quality than raw win rates, because it mathematically removes the confounding effect of answer length. Combined with the Bradley-Terry latent quality scores from Module 2, this constitutes a two-stage calibration pipeline that addresses both schedule-dependency and verbosity bias in LLM-as-a-Judge evaluation systems.