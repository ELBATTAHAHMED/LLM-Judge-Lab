# JudgeLab — LLM-as-a-Judge Reliability & Bias Evaluation Platform

[![Master's PFE](https://img.shields.io/badge/Academic%20Project-Master%202%20Big%20Data-blue.svg)](https://github.com/ELBATTAHAHMED/LLM-Judge-Lab)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19.0-61DAFB.svg?logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6.svg?logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Author:** Ahmed El Battah  
**Degree:** Master 2 Big Data & Artificial Intelligence (PFE - Projet de Fin d'Études)  
**Repository:** [ELBATTAHAHMED/LLM-Judge-Lab](https://github.com/ELBATTAHAHMED/LLM-Judge-Lab)

---

## 📌 Executive Summary

**JudgeLab** is an end-to-end, reproducible empirical research platform and full-stack software suite designed to audit, quantify, and mitigate systematic biases in **LLM-as-a-Judge** evaluation systems (e.g., G-EVAL).

As Large Language Models are increasingly deployed as automated evaluators for pair-wise model comparisons, recent literature highlights significant structural failure modes: **position-order bias**, **verbosity/length inflation**, **format-attraction bias**, and **self-provider preference**. 

JudgeLab addresses these challenges by benchmarking state-of-the-art LLMs—including **OpenAI GPT-4o-mini**, **Anthropic Claude-3 Haiku**, **DeepSeek-V3**, **Meta Llama-3.3 70B Instruct**, and **local Ollama models**—against a ground-truth benchmark of **2,271 human preference decisions** derived from the LMSYS Chatbot Arena Vicuna dataset.

---

## 🔬 Research Methodology & Econometric Models

JudgeLab implements advanced econometric models, inferential statistics, and real-time debiasing protocols:

### 1. Latent Quality Parameter Estimation (Bradley-Terry MLE)
Raw win rates suffer from opponent selection bias. JudgeLab fits a **Bradley-Terry Maximum Likelihood Estimation ($\theta$)** model using `scipy.optimize.minimize` (L-BFGS-B optimization):
$$\mathbb{P}(M_i \succ M_j) = \frac{e^{\theta_i}}{e^{\theta_i} + e^{\theta_j}} = \frac{1}{1 + e^{-(\theta_i - \theta_j)}}$$
This places candidate generative models on a continuous scale of intrinsic merit ($\theta$), accounting for matchup difficulty.

### 2. Length-Neutralized Quality Calibration (OLS Residual Decomposition)
To isolate genuine answer quality from length inflation, JudgeLab executes a 5-fold cross-validated **Ordinary Least Squares (OLS) regression** modeling verdict probability against word-count disparity ($\Delta W = W_A - W_B$):
$$Y_{ij} = \beta_0 + \beta_1 \cdot \Delta W_{ij} + \varepsilon_{ij}$$
The residual $\varepsilon_{ij}$ represents length-neutralized quality, producing calibrated rankings that remove the unfair advantage of artificially verbose responses.

### 3. Systematic Bias Diagnostics
* **Position-Order Bias ($\chi^2$ Significance & In-Flight Flips):** Measures verdict shifts under symmetric candidate swaps ($A \leftrightarrow B$). Evaluated via Chi-Square ($\chi^2$) goodness-of-fit testing.
* **Verbosity Bias ($\rho$ Correlation):** Quantifies correlation between word length delta and judge win allocation.
* **Format-Attraction Bias ($\text{FDR-}p$ Adjusted):** Categorizes candidate answers into `markdown_heavy` vs. `plain_text` and applies **Benjamini-Hochberg False Discovery Rate (FDR)** $p$-value adjustments across domain categories.
* **Self-Preference Bias (Binomial Test):** Evaluates provider family alignment (e.g., GPT judge favoring GPT candidates) via exact binomial tests against baseline win rates.
* **Stochastic Stability Drift:** Evaluates decision variance across repeated trials at non-zero temperature ($\tau = 0.7$).

### 4. Active In-Flight Bias Mitigation Protocols
* **Dual A/B Swap Calibration:** Executes symmetric two-pass evaluation (Pass 1: $A \text{ vs } B$; Pass 2: $B \text{ vs } A$) in parallel threads, automatically flagging order flips and declaring a neutral `TIE` upon divergence.
* **Information Density Prompts:** Implements strict system prompts (`_LENGTH_CALIBRATED_SYSTEM_PROMPT`) penalizing fluff and rewarding substantive factual density per word.
* **Multi-Judge Ensemble Voting:** Aggregates concurrent judgments from heterogeneous model families via majority-rule consensus voting.

---

## 🏗 System Architecture

The platform follows a decoupled, production-grade full-stack architecture:

```
                  ┌─────────────────────────────────────────┐
                  │      React 19 + TypeScript Frontend     │
                  │   (Vite, Recharts, Tailwind CSS UI)     │
                  └────────────────────┬────────────────────┘
                                       │ HTTP / REST API
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │          FastAPI Backend Server         │
                  │  (Endpoints for Stats, Eval, Calib)    │
                  └──────────┬───────────────────┬──────────┘
                             │                   │
               SQLAlchemy    │                   │ Multi-Thread API Calls
                             ▼                   ▼
                  ┌────────────────────┐   ┌────────────────────────┐
                  │ PostgreSQL / DB    │   │ LLM API Providers      │
                  │ (Prompts, Answers, │   │ • OpenAI (GPT-4o-mini) │
                  │  Human Judgments)  │   │ • OpenRouter (DeepSeek)│
                  └────────────────────┘   │ • Local Ollama (Llama) │
                                           └────────────────────────┘
```

### Key Modules:
* **`backend/main.py`**: FastAPI REST API serving 11 endpoints for leaderboard stats, bias telemetry, qualitative bucket inspection, and live evaluation.
* **`backend/judge_engine.py`**: Pure-function evaluation engine executing single-pass G-EVAL, Dual A/B Swaps, length-calibrated evaluations, and ThreadPoolExecutor multi-judge voting.
* **`backend/calculate_latent_quality.py`**: Bradley-Terry MLE solver.
* **`backend/calculate_neutralized_scores.py`**: OLS regression length neutralization module.
* **`backend/analyze_consistency.py`**: Statistical calculation engine for Cohen's $\kappa$, position flips, FDR $p$-value corrections, and self-preference binomial testing.
* **`frontend/src/pages/`**:
  * **LeaderboardPage**: Interactive quality rankings with raw win rate vs. Bradley-Terry $\theta$ vs. Length-Neutralized scores.
  * **DiagnosticsPage**: Real-time diagnostic dashboard for Position, Verbosity, Format, Self-Preference, and Domain Reliability metrics.
  * **QualitativeExplorerPage**: Master-detail transcript inspector spanning 4 research strata (`verbosity`, `forced_choice`, `position_bias`, `baseline_alignment`).
  * **LiveLabPage**: Interactive sandbox for live G-EVAL, Dual A/B Swap, and Multi-Judge Ensemble evaluation.

---

## 📊 Benchmark Dataset

The repository includes the complete ground-truth benchmark dataset located in `data/`:
* `human_judgment.jsonl` (15.9 MB): 2,271 pairwise human preference evaluations from LMSYS Chatbot Arena.
* `question.jsonl`: 80 Vicuna benchmark prompts spanning 8 domain categories.
* `gpt-4.jsonl`, `gpt-3.5-turbo.jsonl`, `claude-v1.jsonl`, `alpaca-13b.jsonl`, `llama-13b.jsonl`: Pre-generated candidate response outputs.
* `qualitative_data/`: Stratified CSV evaluation records and empirical results.

---

## 🚀 Quick Start Guide for Thesis Reviewers

### Prerequisites
* **Python**: 3.11 or higher
* **Node.js**: v18.0 or higher (with `npm`)
* **Database**: PostgreSQL (or default fallback configuration)

---

### Step 1: Clone Repository & Setup Python Environment

```bash
# Clone the repository
git clone https://github.com/ELBATTAHAHMED/LLM-Judge-Lab.git
cd LLM-Judge-Lab

# Create and activate virtual environment
python -m venv .venv

# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

# On Linux / macOS:
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

---

### Step 2: Configure Environment Variables (`.env`)

Create a `.env` file in the project root directory:

```env
# Database Connection (PostgreSQL or local SQLite)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/llm_judge_db

# LLM Provider API Keys
OPENAI_API_KEY=your_openai_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Local Model Provider (Optional for Ollama)
OLLAMA_BASE_URL=http://localhost:11434/v1
```

---

### Step 3: Database Ingestion & Verification

Ingest the benchmark dataset into PostgreSQL:

```bash
# Ingest prompts, answers, and human preference data
python backend/ingest_data.py

# Verify database integrity
python verify_database_evaluations.py
```

---

### Step 4: Launch Backend API Server

```bash
# Start FastAPI server on http://localhost:8000
uvicorn backend.main:app --reload --port 8000
```
*API Swagger Documentation is accessible at `http://localhost:8000/docs`.*

---

### Step 5: Launch Frontend Web Platform

In a new terminal window:

```bash
cd frontend

# Install Node.js dependencies
npm install

# Start Vite React development server
npm run dev
```
*The web platform will open at `http://localhost:5173`.*

---

### Step 6: Automated Test Verification

Run the full automated test suite to verify pipeline correctness:

```bash
pytest tests/test_pipeline.py -v
```

---

## 📄 Thesis Exhibits & Research Artifacts

For complete empirical figures, data tables, and detailed answers to Research Questions (RQ1–RQ6), refer to:
* [`thesis_chapter_5_exhibits.md`](thesis_chapter_5_exhibits.md): Chapter 5 Empirical Thesis Exhibits & Findings.
* [`bradley_terry_report.md`](bradley_terry_report.md): Bradley-Terry Model Fitting Technical Report.
* [`neutralized_scores_report.md`](neutralized_scores_report.md): OLS Residual Neutralization Technical Report.
* [`consistency_report.md`](consistency_report.md): Multi-Turn Consistency & Reliability Analysis Report.

---

## 📜 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
