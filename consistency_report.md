# Experimental Module 1: Multi-Turn Logical Consistency Analysis

> **Research Protocol**: This report measures the LLM judge's logical consistency by analysing whether it preserves a coherent relative quality ordering across different evaluation contexts.

## 1. Overall Consistency Score

| Dimension | Score |
| :--- | :---: |
| Position-Order Consistency | `83.3%` |
| Domain Specialization Rate (Descriptive) | `33.3%` |
| **Composite Logical Consistency Score** | **`83.3%`** |

> **Thesis Interpretation**: The Composite Logical Consistency Score is defined strictly by Position-Order Consistency (verdict invariance under position swapping). Domain Specialization Rate is recorded separately as a neutral descriptive metric representing model category-specific strengths, NOT as an evaluation flaw or inconsistency.

## 2. Position-Order Consistency

Across **120** model-pair / category combinations that appeared in both orderings, **20** exhibited a winner flip depending on which model held Position A.

### Flagged Position Inconsistencies

| Category | Model 1 | Model 2 | Win Rate (M1 in Pos A) | Win Rate (M1 in Pos B) | Verdict |
| :--- | :--- | :--- | :---: | :---: | :--- |
| coding | `gpt-3.5-turbo` | `gpt-4` | 15.4% | 53.8% | **POSITION FLIP DETECTED** |
| extraction | `alpaca-13b` | `llama-13b` | 40.0% | 80.0% | **POSITION FLIP DETECTED** |
| extraction | `claude-v1` | `gpt-3.5-turbo` | 8.3% | 60.0% | **POSITION FLIP DETECTED** |
| extraction | `claude-v1` | `vicuna-13b` | 100.0% | 50.0% | **POSITION FLIP DETECTED** |
| extraction | `gpt-3.5-turbo` | `vicuna-13b` | 56.2% | 38.5% | **POSITION FLIP DETECTED** |
| humanities | `alpaca-13b` | `llama-13b` | 37.5% | 75.0% | **POSITION FLIP DETECTED** |
| humanities | `alpaca-13b` | `vicuna-13b` | 27.3% | 57.1% | **POSITION FLIP DETECTED** |
| humanities | `gpt-3.5-turbo` | `vicuna-13b` | 21.4% | 60.0% | **POSITION FLIP DETECTED** |
| math | `claude-v1` | `vicuna-13b` | 83.3% | 50.0% | **POSITION FLIP DETECTED** |
| math | `gpt-4` | `vicuna-13b` | 66.7% | 44.4% | **POSITION FLIP DETECTED** |
| reasoning | `alpaca-13b` | `claude-v1` | 20.0% | 57.1% | **POSITION FLIP DETECTED** |
| reasoning | `alpaca-13b` | `llama-13b` | 50.0% | 71.4% | **POSITION FLIP DETECTED** |
| reasoning | `alpaca-13b` | `vicuna-13b` | 38.5% | 75.0% | **POSITION FLIP DETECTED** |
| reasoning | `claude-v1` | `llama-13b` | 41.7% | 75.0% | **POSITION FLIP DETECTED** |
| reasoning | `gpt-4` | `vicuna-13b` | 50.0% | 100.0% | **POSITION FLIP DETECTED** |
| roleplay | `claude-v1` | `gpt-4` | 42.9% | 54.5% | **POSITION FLIP DETECTED** |
| stem | `claude-v1` | `vicuna-13b` | 25.0% | 90.9% | **POSITION FLIP DETECTED** |
| stem | `gpt-3.5-turbo` | `vicuna-13b` | 18.2% | 63.6% | **POSITION FLIP DETECTED** |
| writing | `gpt-3.5-turbo` | `vicuna-13b` | 50.0% | 60.0% | **POSITION FLIP DETECTED** |
| writing | `gpt-4` | `vicuna-13b` | 50.0% | 100.0% | **POSITION FLIP DETECTED** |

## 3. Cross-Category Domain Specialization Variance

This section evaluates how relative win rates vary across MT-Bench prompt domains. A pair with `distinct_winners > 1` demonstrates Domain Specialization Variance—where model superiority shifts depending on topic domain (e.g., Coding vs Humanities), reflecting domain-specific capabilities rather than a logical defect.

| Model Pair | Distinct Winners | Domain Specialization Variance |
| :--- | :---: | :---: |
| `alpaca-13b` vs `claude-v1` | 1 | no |
| `alpaca-13b` vs `gpt-3.5-turbo` | 1 | no |
| `alpaca-13b` vs `gpt-4` | 1 | no |
| `alpaca-13b` vs `llama-13b` | 3 | YES |
| `alpaca-13b` vs `vicuna-13b` | 2 | YES |
| `claude-v1` vs `gpt-3.5-turbo` | 2 | YES |
| `claude-v1` vs `gpt-4` | 3 | YES |
| `claude-v1` vs `llama-13b` | 1 | no |
| `claude-v1` vs `vicuna-13b` | 1 | no |
| `gpt-3.5-turbo` vs `gpt-4` | 1 | no |
| `gpt-3.5-turbo` vs `llama-13b` | 1 | no |
| `gpt-3.5-turbo` vs `vicuna-13b` | 2 | YES |
| `gpt-4` vs `llama-13b` | 1 | no |
| `gpt-4` vs `vicuna-13b` | 1 | no |
| `llama-13b` vs `vicuna-13b` | 1 | no |

## 4. Per-Category Win Rates (Selected Pairs)

### `alpaca-13b` vs `llama-13b`

| Category | Total | `alpaca-13b` Win Rate | Category Winner |
| :--- | :---: | :---: | :---: |
| coding | 15 | 86.7% | `alpaca-13b` |
| extraction | 10 | 60.0% | `alpaca-13b` |
| humanities | 12 | 50.0% | `TIE` |
| math | 13 | 15.4% | `llama-13b` |
| reasoning | 11 | 63.6% | `alpaca-13b` |
| roleplay | 12 | 50.0% | `TIE` |
| stem | 14 | 92.9% | `alpaca-13b` |
| writing | 15 | 73.3% | `alpaca-13b` |

### `claude-v1` vs `gpt-4`

| Category | Total | `claude-v1` Win Rate | Category Winner |
| :--- | :---: | :---: | :---: |
| coding | 11 | 45.5% | `gpt-4` |
| extraction | 18 | 22.2% | `gpt-4` |
| humanities | 18 | 27.8% | `gpt-4` |
| math | 19 | 31.6% | `gpt-4` |
| reasoning | 18 | 33.3% | `gpt-4` |
| roleplay | 18 | 50.0% | `TIE` |
| stem | 26 | 65.4% | `claude-v1` |
| writing | 18 | 27.8% | `gpt-4` |

### `alpaca-13b` vs `vicuna-13b`

| Category | Total | `alpaca-13b` Win Rate | Category Winner |
| :--- | :---: | :---: | :---: |
| coding | 15 | 40.0% | `vicuna-13b` |
| extraction | 15 | 6.7% | `vicuna-13b` |
| humanities | 18 | 38.9% | `vicuna-13b` |
| math | 15 | 46.7% | `vicuna-13b` |
| reasoning | 21 | 52.4% | `alpaca-13b` |
| roleplay | 16 | 18.8% | `vicuna-13b` |
| stem | 20 | 10.0% | `vicuna-13b` |
| writing | 20 | 15.0% | `vicuna-13b` |

## 5. Scientific Commentary

The Logical Consistency Score reveals a critical limitation of deterministic pairwise evaluation: the judge's verdicts are not invariant to presentation context. The position of an answer in the prompt (Position A vs B) can influence the judge's relative quality ranking. Domain Specialization Variance, meanwhile, captures topic-specific performance differentials without penalizing the judge's logical validity.