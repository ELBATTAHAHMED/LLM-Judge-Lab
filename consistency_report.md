# Experimental Module 1: Multi-Turn Logical Consistency Analysis

> **Research Protocol**: This report measures the LLM judge's logical consistency by analysing whether it preserves a coherent relative quality ordering across different evaluation contexts.

## 1. Overall Consistency Score

| Dimension | Score |
| :--- | :---: |
| Position-Order Consistency | `88.8%` |
| Cross-Category Consistency | `80.0%` |
| **Composite Logical Consistency Score** | **`84.4%`** |

> **Thesis Interpretation**: A Composite Score below 80% indicates that the judge's rankings are context-dependent rather than reflecting stable quality estimates. This corroborates the need for calibrated scoring methods (see Modules 2 and 3).

## 2. Position-Order Consistency

Across **80** model-pair / category combinations that appeared in both orderings, **9** exhibited a winner flip depending on which model held Position A.

### Flagged Position Inconsistencies

| Category | Model 1 | Model 2 | Win Rate (M1 in Pos A) | Win Rate (M1 in Pos B) | Verdict |
| :--- | :--- | :--- | :---: | :---: | :--- |
| extraction | `alpaca-13b` | `llama-13b` | 50.0% | 62.5% | **POSITION FLIP DETECTED** |
| math | `claude-v1` | `gpt-3.5-turbo` | 22.2% | 54.5% | **POSITION FLIP DETECTED** |
| math | `gpt-3.5-turbo` | `gpt-4` | 12.5% | 58.3% | **POSITION FLIP DETECTED** |
| roleplay | `alpaca-13b` | `llama-13b` | 37.5% | 75.0% | **POSITION FLIP DETECTED** |
| roleplay | `claude-v1` | `gpt-3.5-turbo` | 60.0% | 38.9% | **POSITION FLIP DETECTED** |
| stem | `claude-v1` | `gpt-3.5-turbo` | 50.0% | 87.5% | **POSITION FLIP DETECTED** |
| stem | `claude-v1` | `gpt-4` | 53.3% | 36.4% | **POSITION FLIP DETECTED** |
| writing | `alpaca-13b` | `llama-13b` | 37.5% | 71.4% | **POSITION FLIP DETECTED** |
| writing | `claude-v1` | `gpt-3.5-turbo` | 75.0% | 38.5% | **POSITION FLIP DETECTED** |

## 3. Cross-Category Consistency

This section shows how the winner of each model pair changes across MT-bench categories. A pair with `distinct_winners > 1` indicates the judge switches its preference depending on the topic domain.

| Model Pair | Distinct Winners | Has Contradiction |
| :--- | :---: | :---: |
| `alpaca-13b` vs `claude-v1` | 1 | no |
| `alpaca-13b` vs `gpt-3.5-turbo` | 1 | no |
| `alpaca-13b` vs `gpt-4` | 1 | no |
| `alpaca-13b` vs `llama-13b` | 3 | YES |
| `claude-v1` vs `gpt-3.5-turbo` | 2 | YES |
| `claude-v1` vs `gpt-4` | 1 | no |
| `claude-v1` vs `llama-13b` | 1 | no |
| `gpt-3.5-turbo` vs `gpt-4` | 1 | no |
| `gpt-3.5-turbo` vs `llama-13b` | 1 | no |
| `gpt-4` vs `llama-13b` | 1 | no |

## 4. Per-Category Win Rates (Selected Pairs)

### `alpaca-13b` vs `llama-13b`

| Category | Total | `alpaca-13b` Win Rate | Category Winner |
| :--- | :---: | :---: | :---: |
| coding | 15 | 66.7% | `alpaca-13b` |
| extraction | 10 | 60.0% | `alpaca-13b` |
| humanities | 12 | 75.0% | `alpaca-13b` |
| math | 13 | 23.1% | `llama-13b` |
| reasoning | 11 | 18.2% | `llama-13b` |
| roleplay | 12 | 50.0% | `TIE` |
| stem | 14 | 78.6% | `alpaca-13b` |
| writing | 15 | 53.3% | `alpaca-13b` |

### `claude-v1` vs `gpt-3.5-turbo`

| Category | Total | `claude-v1` Win Rate | Category Winner |
| :--- | :---: | :---: | :---: |
| coding | 19 | 36.8% | `gpt-3.5-turbo` |
| extraction | 17 | 17.6% | `gpt-3.5-turbo` |
| humanities | 26 | 76.9% | `claude-v1` |
| math | 20 | 40.0% | `gpt-3.5-turbo` |
| reasoning | 18 | 66.7% | `claude-v1` |
| roleplay | 28 | 46.4% | `gpt-3.5-turbo` |
| stem | 18 | 66.7% | `claude-v1` |
| writing | 29 | 58.6% | `claude-v1` |

### `alpaca-13b` vs `gpt-3.5-turbo`

| Category | Total | `alpaca-13b` Win Rate | Category Winner |
| :--- | :---: | :---: | :---: |
| coding | 16 | 6.2% | `gpt-3.5-turbo` |
| extraction | 28 | 21.4% | `gpt-3.5-turbo` |
| humanities | 36 | 11.1% | `gpt-3.5-turbo` |
| math | 26 | 0.0% | `gpt-3.5-turbo` |
| reasoning | 23 | 17.4% | `gpt-3.5-turbo` |
| roleplay | 26 | 3.8% | `gpt-3.5-turbo` |
| stem | 22 | 9.1% | `gpt-3.5-turbo` |
| writing | 23 | 17.4% | `gpt-3.5-turbo` |

## 5. Scientific Commentary

The Logical Consistency Score reveals a critical limitation of deterministic pairwise evaluation: the judge's verdicts are not invariant to presentation context. Both the position of an answer in the prompt (Position A vs B) and the domain category of the question influence the judge's relative quality ranking. This means that raw win-rate leaderboards—where a model's score depends on which opponents it faced and in which order—are fundamentally unstable. The Bradley-Terry Latent Quality Scores (Module 2) address this by estimating intrinsic quality parameters that account for opponent strength, while the Length-Neutralized Scores (Module 3) isolate true quality from verbosity effects.