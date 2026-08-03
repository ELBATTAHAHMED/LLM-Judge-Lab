# 🔬 JudgeLab: LLM-as-a-Judge Reliability & Bias Evaluation Platform

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
4. **Self-Preference Bias**: Self-enhancement tendency of judge models favoring their own generated completions.
5. **Stochastic Non-Determinism**: Output fluctuations across repeated trials even at temperature $T = 0.0$.

**JudgeLab** is a full-stack, scientific research platform and active bias mitigation suite built to measure, diagnose, and algorithmically calibrate automated LLM evaluators. Using **2,271 paired human preference matchups** across 6 candidate models evaluated by 4 distinct judge architectures (`GPT-4o-Mini`, `DeepSeek-V3 Chat`, `Llama-3.3-70B-Instruct`, `Claude-3-Haiku`), JudgeLab transforms raw LLM verdicts into calibrated, unbiased evaluation metrics.

---

## 🏛️ System Architecture

```
LLM-Judge-Lab/
├── backend/
│   ├── database.py                   # SQLAlchemy engine & session factory
│   ├── models.py                     # PostgreSQL ORM domain models
│   ├── judge_engine.py               # G-EVAL & Multi-Judge Ensemble Voting Engine
│   ├── main.py                       # FastAPI REST routes & PostgreSQL decision handlers
│   ├── analyze_results.py            # Statistical tests (Kappa, Chi2, Spearman, Binomial)
│   ├── analyze_consistency.py        # Multi-turn & inter-judge reliability (FDR adjustment)
│   ├── calculate_latent_quality.py   # Bradley-Terry MLE solver (SciPy optimization)
│   ├── calculate_neutralized_scores.py # OLS length-bias neutralization
│   ├── extract_qualitative_data.py   # Qualitative data extraction script
│   ├── generate_perturbations.py     # Standalone CLI perturbation generator
│   ├── stochastic_test.py            # Standalone CLI non-zero temperature test
│   ├── ingest_data.py                # PostgreSQL benchmark dataset dynamic seeder
│   └── verify_db.py                  # Database integrity checker
├── data/                             # Raw benchmark JSONL dataset files
├── qualitative_data/                 # Per-judge segregated qualitative reasoning CSVs
├── frontend/
│   ├── src/
│   │   ├── api/                      # Axios HTTP client & TypeScript interfaces
│   │   ├── components/               # Specialized Recharts visualizers & UI controls
│   │   ├── context/                  # React Judge & Theme state providers
│   │   ├── layouts/                  # Global responsive navigation layout
│   │   ├── pages/                    # Leaderboard, Diagnostics, Qualitative, LiveLab
│   │   └── App.tsx                   # Main React router
│   ├── package.json
│   └── vite.config.ts
├── tests/                            # Automated PyTest & Vitest suites
│   ├── test_pipeline.py              # PyTest backend integration suite
│   └── components/                   # Vitest frontend component tests
├── requirements.txt                  # Frozen Python dependencies
└── README.md                         # Thesis platform documentation
```

---

## 🚀 Core Platform Features & Workflows

### 1. Unified Ranks & Leaderboard
- **Bradley-Terry Latent Quality Scores ($\theta$)**: Computes Maximum Likelihood Estimation (MLE) latent strength parameters with reference model constraint ($\theta_{\text{alpaca-13b}} = 0.0$).
- **Length Neutralization**: Fits OLS linear regression slopes ($\beta$) to compute residual neutralized win rates ($W_{\text{net}} = W_A - \beta(L_A - L_B)$).

### 2. Bias Diagnostics Workspace
- **Verbosity Bias Analysis**: Quantifies length slope $\beta$, standard error, $R^2$, and Spearman rank correlation ($\rho$).
- **Position Bias Analysis**: Computes binary $\chi^2$ test statistic and $p$-value for presentation order symmetry.
- **Self-Preference Bias Analysis**: Computes self-enhancement rates and exact Binomial test $p$-values.
- **Inter-Judge Agreement Matrix**: Cross-judge Cohen's $\kappa$ and pairwise percentage agreement matrix ($N = 2,271$ overlapping pairs).

### 3. Qualitative Explorer
- **Verbatim Rationale Inspector**: Side-by-side text comparison, word count differences, human winner vs AI winner, and syntax-highlighted verbatim judge rationale.

### 4. Interactive Live Sandbox (Standard, Calibrated & Multi-Judge Ensemble)
- **Standard G-EVAL Trial**: Single-pass pairwise comparison with verbatim reasoning.
- **Dual A/B Swap Calibration**: Symmetric two-pass execution (Original Order: A vs B, Swapped Order: B vs A) detecting order flips in flight.
- **Multi-Judge Ensemble Voting**: Concurrent ThreadPoolExecutor execution across 3 selected judge models, aggregating individual votes into a majority consensus verdict with single-model failure tolerance.

---

## 📊 Empirical Findings Summary (4 Judge Architectures)

| Evaluator Judge Model | Bradley-Terry Top Model ($\theta$) | Length Slope ($\beta$) | Human Cohen's $\kappa$ | Position $\chi^2$ ($p$-val) | Inter-Judge $\kappa$ vs `gpt-4o-mini` |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **GPT-4o-Mini** | `gpt-4` (+2.7912) | $+0.000679$ ($p < 10^{-28}$) | 0.3298 | 4.790 ($p = 0.0286$) | 1.0000 (Self) |
| **DeepSeek-V3 Chat** | `gpt-4` (+2.1934) | $+0.000420$ ($p < 10^{-10}$) | 0.3023 | 25.215 ($p < 10^{-5}$) | 0.5434 (72.74% agree) |
| **Llama-3.3-70B-Instruct** | `gpt-4` (+2.4796) | $+0.000583$ ($p < 10^{-22}$) | 0.3147 | 1.277 ($p = 0.2584$) | 0.5465 (71.33% agree) |
| **Claude-3-Haiku** | `claude-v1` (+2.8947) | $+0.000744$ ($p < 10^{-43}$) | 0.3261 | 1.445 ($p = 0.2294$) | 0.3463 (56.54% agree) |

---

## 🛠️ Step-by-Step Installation & Setup

### Prerequisites
- **Python**: 3.11 or higher
- **Node.js**: v18 or higher (with `npm`)
- **PostgreSQL**: Local or remote server running PostgreSQL

---

### Step 1: Database Initialization

1. Start your local PostgreSQL service.
2. Create a database named `judgelab`:
```sql
CREATE DATABASE judgelab;
CREATE USER postgres WITH PASSWORD 'postgres';
GRANT ALL PRIVILEGES ON DATABASE judgelab TO postgres;
```

---

### Step 2: Backend Setup

1. Open a terminal in the project root directory (`llm-judge-lab`).
2. Activate your Python virtual environment:
   ```bash
   # On Windows (PowerShell)
   .\.venv\Scripts\Activate.ps1

   # On Linux / macOS
   source .venv/bin/activate
   ```
3. Install backend dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure your `.env` file in the root directory:
   ```env
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/judgelab
   OPENAI_API_KEY=your_openai_api_key_here
   OPENROUTER_API_KEY=your_openrouter_api_key_here
   ```
5. Ingest the benchmark evaluation dataset into PostgreSQL:
   ```bash
   python backend/ingest_data.py
   ```
6. Launch the FastAPI backend server:
   ```bash
   uvicorn backend.main:app --reload --port 8000
   ```
   Interactive OpenAPI docs available at `http://localhost:8000/docs`.

---

### Step 3: Frontend Setup

1. Open a new terminal in the `frontend/` directory.
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the Vite React development server:
   ```bash
   npm run dev
   ```
4. Open `http://localhost:5173` in your browser.

---

## 🧪 Automated Testing

```bash
# Execute PyTest backend integration suite
pytest tests/test_pipeline.py -s

# Execute Vitest frontend unit tests
cd frontend && npx vitest run

# Verify production frontend build
npm run build
```

---

## 📜 License

This project is licensed under the **MIT License**.
