# 🔬 JudgeLab: LLM-as-a-Judge Reliability Lab

**Measuring, Diagnosing, and Algorithmically Neutralizing Systemic Biases in LLM Evaluators**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-green.svg)](https://www.python.org/)
[![React: 18](https://img.shields.io/badge/React-18-blue.svg)](https://reactjs.org/)
[![FastAPI: 0.111+](https://img.shields.io/badge/FastAPI-0.111+-teal.svg)](https://fastapi.tiangolo.com/)
[![Vite: 6](https://img.shields.io/badge/Vite-6-purple.svg)](https://vitejs.dev/)
[![Build: Passing](https://img.shields.io/badge/Build-100%25%20Passing-emerald.svg)]()

---

## 👨‍🎓 Academic Context & Executive Overview

* **Author:** Ahmed El Battah  
* **Academic Program:** Master 2 Intelligent Processing Systems (IPS) — Master's Thesis / Projet de Fin d'Études (PFE)  
* **Project Name:** LLM-as-a-Judge Reliability Lab (**JudgeLab**)  
* **Domain:** Artificial Intelligence, Natural Language Generation (NLG) Evaluation, Applied Econometrics & Data Science  

### Overview
Large Language Models (LLMs) are increasingly deployed as automated evaluators (*LLM-as-a-Judge*) to evaluate, score, and rank model-generated text. However, empirical evaluation proves that raw LLM judge win rates are confounded by structural and cognitive biases:
1. **Verbosity Bias**: Systematic preference for longer candidate responses regardless of factual accuracy or conciseness.
2. **Position Order Bias**: Systematic preference for candidate answers presented first (Position A) or second (Position B).
3. **Format Bias**: Structural preference for Markdown-rendered text over plain-text responses.
4. **Stochastic Non-Determinism**: Output fluctuations across repeated trials even at temperature $T = 0.0$.

**JudgeLab** is a full-stack, scientific research platform and active bias mitigation suite built to measure, diagnose, and algorithmically calibrate automated LLM evaluators. Using **2,271 paired human preference matchups** across 6 candidate models (`alpaca-13b`, `claude-v1`, `gpt-3.5-turbo`, `gpt-4`, `llama-13b`, `vicuna-13b`) evaluated by 4 distinct judge architectures (`GPT-4o-Mini`, `DeepSeek-V3 Chat`, `Llama-3.3-70B-Instruct`, `Claude-3-Haiku`), JudgeLab transforms raw LLM verdicts into calibrated, unbiased evaluation metrics.

---

## 🚀 Core Platform Features & Workflows

### 1. Unified Ranks & Leaderboard
- **Bradley-Terry Latent Quality Scores ($\theta$)**: Computes Maximum Likelihood Estimation (MLE) latent strength parameters with reference model constraint ($\theta_{\text{alpaca-13b}} = 0.0$).
- **5-Fold Cross-Validated Length Neutralization**: Fits OLS regression slopes ($\beta$) to compute residual neutralized win rates ($W_{\text{net}} = W_A - \beta(L_A - L_B)$) out-of-sample on holdout folds.

### 2. Bias Diagnostics Workspace
- **Verbosity Bias Analysis**: Quantifies length slope $\beta$, standard error, $R^2$, and Spearman rank correlation ($\rho$).
- **Position Bias Analysis**: Computes binary $\chi^2$ test statistic and $p$-value for presentation order symmetry.
- **Domain Reliability & Format Bias**: Category-stratified Cohen's $\kappa$ agreement with human judges and Markdown vs plain text preference tests.
- **Inter-Judge Agreement Matrix**: Cross-judge Cohen's $\kappa$ and pairwise percentage agreement matrix ($N = 2,271$ overlapping pairs).

### 3. Qualitative Explorer
- **Segregated Per-Model Reasoning Disk Data**: Dedicated subdirectories for all 4 judge models (`gpt-4o-mini`, `deepseek_deepseek-chat`, `meta-llama_llama-3.3-70b-instruct`, `anthropic_claude-3-haiku`).
- **Verbatim Chain-of-Thought Rationale**: Side-by-side text comparison, word count differences, human winner vs AI winner, and verbatim judge rationale.

### 4. Live Lab (Standard & Calibrated G-EVAL Sandbox)
- **Real-Time Dual A/B Swap Calibration**: Symmetric two-pass pairwise execution (Original Order: A vs B, Swapped Order: B vs A) detecting position flips in flight.
- **Database Persistence**: Automatic insertion of live evaluation runs into the PostgreSQL database.

### 5. Experiment Control Center (ECC)
- **Batch Evaluation Engine**: Execute strata batch evaluation runs across custom sample sizes and mitigation strategies.
- **Synthetic Perturbation Generator**: Inject controlled verbosity padding ($10\% - 50\%$) and Markdown formatting transformations.
- **Stochastic Benchmark Suite**: Multi-trial repetition passes ($N=5, 10, 20$) measuring flip rates at temperature $T=0.0$.

---

## 📊 Empirical Findings Summary (4 Judge Architectures)

| Evaluator Judge Model | Bradley-Terry Top Model ($\theta$) | Length Slope ($\beta$) | Human Cohen's $\kappa$ | Position $\chi^2$ ($p$-val) | Inter-Judge $\kappa$ vs `gpt-4o-mini` |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **GPT-4o-Mini** | `gpt-4` (+2.7912) | $+0.000679$ ($p < 10^{-28}$) | 0.3298 | 4.790 ($p = 0.0286$) | 1.0000 (Self) |
| **DeepSeek-V3 Chat** | `gpt-4` (+2.1934) | $+0.000420$ ($p < 10^{-10}$) | 0.3023 | 25.215 ($p < 10^{-5}$) | 0.5434 (72.74% agree) |
| **Llama-3.3-70B-Instruct** | `gpt-4` (+2.4796) | $+0.000583$ ($p < 10^{-22}$) | 0.3147 | 1.277 ($p = 0.2584$) | 0.5465 (71.33% agree) |
| **Claude-3-Haiku** | `claude-v1` (+2.8947) | $+0.000744$ ($p < 10^{-43}$) | 0.3261 | 1.445 ($p = 0.2294$) | 0.3463 (56.54% agree) |

---

## 🛠️ Step-by-Step Getting Started Guide

### Prerequisites
- **Python**: 3.11 or higher
- **Node.js**: v18 or higher (with `npm`)
- **PostgreSQL**: Local or remote server running PostgreSQL

---

### Step 1: Database Initialization

1. Start your local PostgreSQL service.
2. Create a database named `judgelab` and user `postgres` (or use your existing credentials):
```sql
CREATE DATABASE judgelab;
CREATE USER postgres WITH PASSWORD 'postgres';
GRANT ALL PRIVILEGES ON DATABASE judgelab TO postgres;
```

---

### Step 2: Backend Setup

1. Open a terminal in the project root directory (`LLM-Judge-Lab`).
2. Create and activate a Python virtual environment:
   ```bash
   # On Windows (PowerShell)
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1

   # On Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install frozen Python dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```
4. Configure your environment variables in `.env` (create a `.env` file in the root directory if missing):
   ```env
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/judgelab
   OPENAI_API_KEY=your_openai_api_key_here
   OPENROUTER_API_KEY=your_openrouter_api_key_here
   ```
5. Ingest the benchmark evaluation dataset into PostgreSQL:
   ```bash
   python backend/ingest_data.py
   ```
6. Launch the FastAPI development server:
   ```bash
   uvicorn backend.main:app --reload --port 8000
   ```
   The backend API documentation will be accessible at `http://localhost:8000/docs`.

---

### Step 3: Frontend Setup

1. Open a new terminal window in the project root directory.
2. Navigate to the `frontend` folder:
   ```bash
   cd frontend
   ```
3. Install Node package dependencies:
   ```bash
   npm install
   ```
4. Start the Vite React development server:
   ```bash
   npm run dev
   ```
5. Open your web browser and navigate to `http://localhost:5173`.

---

## 🏗️ Architecture & Technology Stack

```
LLM-Judge-Lab/
├── backend/
│   ├── database.py                   # SQLAlchemy engine & session factory
│   ├── models.py                     # PostgreSQL ORM domain models
│   ├── judge_engine.py               # G-EVAL engine (OpenAI / OpenRouter / Ollama)
│   ├── main.py                       # FastAPI REST routes & background job orchestrators
│   ├── analyze_results.py            # Statistical tests (Kappa, Chi2, Spearman)
│   ├── analyze_consistency.py        # Multi-turn & inter-judge reliability
│   ├── calculate_latent_quality.py   # Bradley-Terry MLE solver (SciPy)
│   ├── calculate_neutralized_scores.py # OLS length-bias neutralization (5-fold CV)
│   ├── extract_qualitative_data.py   # Qualitative data extraction script
│   ├── generate_perturbations.py     # Synthetic verbosity/format perturbation engine
│   ├── stochastic_test.py            # Temperature=0.0 stochastic variance tester
│   ├── ingest_data.py                # PostgreSQL benchmark dataset seeder
│   └── requirements.txt              # Frozen Python dependencies
├── data/                             # Raw MT-Bench JSONL dataset files
├── qualitative_data/                 # Per-judge segregated qualitative reasoning CSVs
│   ├── anthropic_claude-3-haiku/
│   ├── deepseek_deepseek-chat/
│   ├── gpt-4o-mini/
│   └── meta-llama_llama-3.3-70b-instruct/
├── frontend/
│   ├── src/
│   │   ├── api/                      # Axios HTTP client & TypeScript interfaces
│   │   ├── components/               # Specialized Recharts visualizers & UI controls
│   │   ├── context/                  # React Judge & Theme state providers
│   │   ├── hooks/                    # Job progress polling hook
│   │   ├── pages/                    # Leaderboard, Diagnostics, Qualitative, LiveLab, ECC
│   │   └── App.tsx                   # Main router configuration
│   └── package.json
└── README.md
```

---

## 🧪 Verification & Automated Testing

To run the backend statistical test suite and verify database integrity:
```bash
# Execute pytest suite
pytest

# Verify PostgreSQL database row counts and model consistency
python backend/verify_db.py

# Verify frontend build compilation
cd frontend && npm run build
```

---

## 📜 License

This project is licensed under the **MIT License**.
