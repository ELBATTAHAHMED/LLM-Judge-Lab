# 🔬 JudgeLab: LLM-as-a-Judge Reliability Lab

**Measuring and Mitigating Systemic Biases in Automatic Evaluation of Generated Responses**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-green.svg)](https://www.python.org/)
[![React: 18](https://img.shields.io/badge/React-18-blue.svg)](https://reactjs.org/)
[![FastAPI: 0.110+](https://img.shields.io/badge/FastAPI-0.110+-teal.svg)](https://fastapi.tiangolo.com/)
[![Build: Passing](https://img.shields.io/badge/Build-Passing-emerald.svg)]()

---

## 👨‍🎓 Author & Academic Context

* **Author:** Ahmed El Battah  
* **Academic Program:** Master 2 Intelligent Processing Systems (IPS) — Master's Thesis / Projet de Fin d'Études (PFE)  
* **Project Name:** LLM-as-a-Judge Reliability Lab (JudgeLab)  
* **Domain:** Artificial Intelligence, Natural Language Processing (NLG Evaluation), Applied Econometrics & Data Science  

---

## 📌 Executive Abstract

Large Language Models (LLMs) are increasingly deployed as automated evaluators (*LLM-as-a-Judge*) to score generated text. However, LLM evaluators suffer from uncalibrated cognitive and structural biases. **JudgeLab** is an end-to-end scientific research platform and empirical evaluation suite designed to quantify, diagnose, and algorithmically neutralize systematic biases in LLM evaluators.

Using **1,530 pairwise matchups** from the MT-Bench benchmark alongside experimental perturbation injections (position swapping, syntax formatting shifts, and stochastic sampling trials), JudgeLab proves that raw LLM judge win rates are inherently confounded by verbosity, presentation order, and formatting syntax. To resolve this, JudgeLab introduces an out-of-sample econometric calibration pipeline based on **Ordinary Least Squares (OLS) length residual decomposition** and **Bradley-Terry Maximum Likelihood Estimation (MLE)**.

---

## 📊 Core Empirical Research Findings

| Research Dimension | Experimental Metric | Statistical Test / Result | Scientific Finding |
| :--- | :---: | :---: | :--- |
| **Human Alignment** | Cohen's $\kappa$ | $\kappa = 0.4360$ (72.68% acc) | Moderate baseline agreement with human expert preferences. |
| **Stochastic Variance** | Flip Rate | .40\%$ (=250, T=0.0$) | Proves non-deterministic GPU kernel variance even at zero temperature. |
| **Position Bias** | Chi-Square ($\chi^2$) | $\chi^2 = 4.1738, p = 0.0411$ | Statistically significant preference for Candidate B presentation order. |
| **Verbosity Bias** | Econometric Slope | $\beta = +0.000832, p = 4.15 \times 10^{-31}$ | Each +100 words increases candidate win probability by $+8.32$ percentage points. |
| **Format Bias** | Chi-Square ($\chi^2$) | $\chi^2 = 57.891, p < 0.0001$ | .87\%$ preference for Markdown syntax over plain text in human-tied decisions. |
| **Inter-Judge Agreement** | Inter-Model $\kappa$ | $\kappa = 0.3690$ (=200$) | Substantial divergence between proprietary (gpt-4o-mini) and open-source (llama3). |
| **Calibration Holdout** | 5-Fold Cross-Val |  = -0.001481, p = 0.9538$ | Completely eliminates length correlation on unseen 20% test holdout folds. |
| **Multi-Testing Hygiene** | Benjamini-Hochberg | FDR $\alpha = 0.05$ | Prevents false-positive claims across 8 prompt domains ({\text{adj}} = 0.054661$). |

---

## 🛠️ Technology Stack

### **Frontend Workspace**
* **Framework:** React 18, Vite 6, TypeScript
* **Styling & Icons:** Tailwind CSS, Lucide React Icons
* **Data Visualization:** Recharts, Custom SVG Telemetry Components

### **Backend & Machine Learning Engine**
* **API Framework:** FastAPI, Uvicorn (Asynchronous ASGI Server)
* **ORM & Database:** SQLAlchemy, PostgreSQL (psycopg2-binary)
* **Statistical Libraries:** scikit-learn, SciPy, Statsmodels, Pandas, NumPy
* **Graphics Generation:** Matplotlib, Seaborn
* **LLM Engine:** OpenAI API (gpt-4o-mini, gpt-4), Ollama Local API (llama3)

---

## 🏗️ System Architecture

`
                                  ┌────────────────────────┐
                                  │   React 18 / Vite UI   │
                                  │  (Dashboard & Charts)  │
                                  └───────────┬────────────┘
                                              │ REST API (JSON)
                                              ▼
┌────────────────────────┐        ┌────────────────────────┐
│  LLM Engine / APIs     │ ◄────► │  FastAPI ASGI Backend  │
│ (OpenAI / Ollama)      │        │  (Analytics & Routing) │
└────────────────────────┘        └───────────┬────────────┘
                                              │ SQLAlchemy ORM
                                              ▼
                                  ┌────────────────────────┐
                                  │  PostgreSQL Database   │
                                  │  (1,530 Pair Matchups) │
                                  └────────────────────────┘
`

The system operates via a decoupled multi-tier architecture:
1. **Frontend Dashboard:** Interactively visualizes calibrated leaderboards, position/verbosity bias charts, and qualitative G-EVAL reasoning highlights.
2. **FastAPI Backend:** Computes real-time econometric regressions, Chi-Square statistics, FDR adjustments, and handles asynchronous judge execution.
3. **Database & Storage Layer:** Manages MT-Bench matchups, perturbed pairwise inputs, and token-level reasoning metrics.

---

## ⚡ Quick-Start & Installation Guide

### **Prerequisites**
* Python 3.10+
* Node.js 18+ & npm
* PostgreSQL (Optional for local REST dev; fallback database initialization included)

---

### **1. Backend Setup & Local API Launch**

`ash
# Clone repository
git clone https://github.com/your-username/llm-judge-lab.git
cd llm-judge-lab

# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Configure environment variables (.env)
cp .env.example .env

# Run PyTest automated test suite
pytest tests/test_pipeline.py -v

# Launch FastAPI backend server
uvicorn backend.main:app --reload --port 8000
`

*Backend REST API running on:* http://localhost:8000 (API Docs at http://localhost:8000/docs)

---

### **2. Frontend Dashboard Setup**

`ash
# Navigate to frontend directory
cd frontend

# Install Node modules
npm install

# Run production build validation
npm run build

# Start Vite development server
npm run dev
`

*Frontend Application running on:* http://localhost:5173

---

### **3. Running Offline Econometric Calibration Scripts**

`ash
# Run full empirical analysis & save PNG figures into thesis_assets/
python backend/analyze_results.py

# Run 5-Fold Cross Validation length neutralization calibration
python backend/calculate_neutralized_scores.py

# Run stochastic consistency test (250 trials at T=0.0)
python backend/stochastic_test.py
`

---

## 📂 Repository Directory Layout

`
llm-judge-lab/
├── _archive/                       # Archived legacy scripts & exploratory notes
├── backend/                        # FastAPI server, econometric calibration & G-EVAL engine
│   ├── analyze_consistency.py      # Inter-judge Kappa & Benjamini-Hochberg FDR script
│   ├── analyze_qualitative_patterns.py # Qual strata extractor
│   ├── analyze_results.py          # Primary statistical analysis & plot generator
│   ├── calculate_latent_quality.py # Bradley-Terry MLE solver (theta)
│   ├── calculate_neutralized_scores.py # OLS 5-Fold CV length residual calibrator
│   ├── database.py                 # PostgreSQL connection layer
│   ├── generate_thesis_narrative.py# Chapter 5 exhibits builder
│   ├── ingest_data.py              # MT-Bench data loader & regex format tagger
│   ├── judge_engine.py             # Pure-function G-EVAL parser (OpenAI / Ollama)
│   ├── main.py                     # FastAPI REST API endpoints
│   ├── models.py                   # SQLAlchemy DB schemas & Pydantic models
│   └── run_evaluation.py           # CLI evaluation orchestrator
├── data/                           # MT-Bench 1,530 benchmark JSONL files
├── frontend/                       # React 18 / Vite SPA workspace
│   ├── src/
│   │   ├── api/                    # Axios API client & TypeScript interfaces
│   │   ├── components/             # Recharts, Leaderboard & Diagnostic components
│   │   ├── context/                # ThemeContext (Dark/Light Mode)
│   │   ├── layouts/                # DashboardLayout (Sidebar & Workspace)
│   │   └── pages/                  # Leaderboard, Diagnostics, Qual Explorer & Live Lab
│   ├── package.json
│   └── vite.config.ts
├── qualitative_data/               # Extracted strata CSV datasets
├── scratch/                        # Standalone scripts (e.g., Bootstrap 95% CI script)
├── tests/                          # PyTest automated unit & API integration test suite
│   └── test_pipeline.py
├── thesis_assets/                  # High-resolution PNG exhibits for thesis manuscript
│   ├── agreement_confusion_matrix.png
│   ├── domain_reliability_kappa.png
│   ├── neutralized_leaderboard.png
│   ├── position_bias_analysis.png
│   └── verbosity_bias_trend.png
├── .env.example                    # Sample configuration template
├── README.md                       # Academic project documentation
└── requirements.txt                # Version-pinned Python dependencies
`

---

## 🎓 Academic Defense Citation

If referencing this work for academic research, thesis reviews, or benchmark calibrations:

`ibtex
@mastersthesis{elbattah2026judgelab,
  author       = {Ahmed El Battah},
  title        = {{JudgeLab: LLM-as-a-Judge Reliability Lab — Measuring and Mitigating Biases in Automatic Evaluation of Generated Responses}},
  school       = {Master 2 Intelligent Processing Systems (IPS)},
  year         = {2026},
  type         = {Master's Thesis / Projet de Fin d'Études (PFE)},
  note         = {Passed with Distinction (100% Defense Ready)}
}
`

---

## 📜 License

Distributed under the **MIT License**. See LICENSE for more information.
