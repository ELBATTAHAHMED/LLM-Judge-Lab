# 🔬 JudgeLab: LLM-as-a-Judge Reliability Lab

**Measuring and Algorithmically Neutralizing Systemic Biases in LLM Evaluators**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-green.svg)](https://www.python.org/)
[![React: 18](https://img.shields.io/badge/React-18-blue.svg)](https://reactjs.org/)
[![FastAPI: 0.111+](https://img.shields.io/badge/FastAPI-0.111+-teal.svg)](https://fastapi.tiangolo.com/)
[![Vite: 6](https://img.shields.io/badge/Vite-6-purple.svg)](https://vitejs.dev/)
[![Build: Passing](https://img.shields.io/badge/Build-100%25%20Passing-emerald.svg)]()

---

## 👨‍🎓 Academic Context & Executive Purpose

* **Author:** Ahmed El Battah  
* **Academic Program:** Master 2 Intelligent Processing Systems (IPS) — Master's Thesis / Projet de Fin d'Études (PFE)  
* **Project Name:** LLM-as-a-Judge Reliability Lab (**JudgeLab**)  
* **Domain:** Artificial Intelligence, Natural Language Generation (NLG) Evaluation, Applied Econometrics & Data Science  

### High-Level Purpose
Large Language Models (LLMs) are increasingly deployed as automated evaluators (*LLM-as-a-Judge*) to score and rank model-generated responses. However, empirical findings prove that raw LLM judge win rates are confounded by structural and cognitive biases:
1. **Verbosity Bias**: Systematic preference for longer, verbose candidate responses regardless of quality.
2. **Position Order Bias**: Systematic preference for candidate answers placed first (Position A) or second (Position B).
3. **Format Bias**: Structural preference for Markdown-rendered text over plain text.
4. **Stochastic Variance**: Non-deterministic verdict fluctuations across identical repeated trials.

**JudgeLab** is an end-to-end scientific research platform and active bias mitigation suite designed to quantify, diagnose, and algorithmically calibrate automated LLM evaluators. Using **1,530 pairwise matchups** from the MT-Bench benchmark alongside synthetic perturbation pipelines and econometric length residual decomposition, JudgeLab transforms raw LLM judge outputs into calibrated, reliable evaluation metrics.

---

## 🖼️ Application Interface & System Mockups

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│  🔬 JudgeLab | LLM-as-a-Judge Reliability Lab                             [Theme: Dark] [API: Connected] │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  [ Leaderboard ]   [ Bias Diagnostics ]   [ Live Evaluation Sandbox ]   [ Experiment Control Center ]    │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                          │
│  LIVE EVALUATION SANDBOX (Active Bias Mitigation Protocol)                                              │
│  ┌──────────────────────────────────────────────────┐  ┌──────────────────────────────────────────────┐  │
│  │ Prompt: "Explain quantum computing simply."      │  │ ACTIVE MITIGATION RESULTS                    │  │
│  │ Model: gpt-4o-mini | Protocol: Dual A/B Swap    │  │ -------------------------------------------- │  │
│  │                                                  │  │ Pass 1 Verdict (A vs B) : WINNER B           │  │
│  │ Answer A (32 words):                             │  │ Pass 2 Verdict (B vs A) : WINNER B (Mapped A)│  │
│  │ "Quantum computing uses qubits..."               │  │ Position Bias Detected : TRUE (Order Flip)   │  │
│  │                                                  │  │ -------------------------------------------- │  │
│  │ Answer B (110 words):                            │  │ FINAL CALIBRATED VERDICT: TIE                │  │
│  │ "Quantum computing processes data using..."      │  │                                              │  │
│  │                                                  │  │ [✓ In-Flight Calibration Complete]           │  │
│  │ [▶ Run Calibrated Evaluation]  [↺ Reset]         │  │                                              │  │
│  └──────────────────────────────────────────────────┘  └──────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Core Platform Features

### 1. Live Evaluation Sandbox (Active Mitigation Protocol)
- **Real-Time Dual A/B Position Swapping**: Executes symmetric two-pass pairwise comparisons (Original Order: A vs B, Swapped Order: B vs A) in parallel to detect position bias flips and return calibrated consensus verdicts.
- **In-Flight Length Penalization**: Applies word-count residual penalty adjustments dynamically during live G-EVAL trials.
- **Verbatim G-EVAL Reasoning Inspector**: Displays verbatim chain-of-thought judge rationale alongside token usage stats.
- **Zero-Mock Architecture**: Integrates directly with OpenAI (`gpt-4o-mini`, `gpt-4`) and local Ollama instances (`llama3`) with zero mock fallbacks.

### 2. Experiment Control Center (Empirical Benchmark Suite)
- **Batch Processing Engine**: Launch background batch evaluations across MT-Bench prompt pair strata ($N = 20, 50, 100$) using configurable mitigation logic.
- **Synthetic Perturbation Generator**: Inject controlled verbosity padding factors ($10\% - 50\%$) and Markdown formatting transformations to stress-test judge robustness.
- **Stochastic Benchmark Trials**: Execute multi-trial repetition passes ($N=5, 10, 20$) at temperature $T=0.0$ to measure GPU floating-point non-determinism and flip variance.
- **Real-Time SSE Telemetry & Short Polling**: Live Server-Sent Events (SSE) stream job logs, percentage progress, and benchmark results directly to the React dashboard.

### 3. Econometric Calibration & Diagnostics Workspace
- **Length Residual Decomposition**: Ordinary Least Squares (OLS) regression decouples raw win rates into true latent quality scores ($lpha_i$) and verbosity slope ($eta \cdot \Delta	ext{WC}$).
- **Bradley-Terry MLE Solver**: Computes scale-invariant latent strength parameters using Maximum Likelihood Estimation over pairwise win/loss matrices.
- **Domain Reliability & Chi-Square Hygiene**: Stratified Cohen's Kappa ($\kappa$) analysis across prompt domains with Benjamini-Hochberg (BH) False Discovery Rate (FDR) control ($lpha = 0.05$).

---

## 📊 Core Empirical Findings

| Research Dimension | Experimental Metric | Statistical Test / Metric | Scientific Finding |
| :--- | :---: | :---: | :--- |
| **Human Alignment** | Cohen's $\kappa$ | $\kappa = 0.4360$ (72.68% acc) | Moderate baseline agreement with human expert preferences. |
| **Stochastic Variance** | Flip Rate | $7.40\%$ ($N=250, T=0.0$) | Proves non-deterministic GPU kernel variance even at zero temperature. |
| **Position Bias** | Chi-Square ($\chi^2$) | $\chi^2 = 4.1738, p = 0.0411$ | Statistically significant preference for Candidate B presentation order. |
| **Verbosity Bias** | Econometric Slope | $eta = +0.000832, p = 4.15 	imes 10^{-31}$ | Each +100 words increases candidate win probability by $+8.32$ percentage points. |
| **Format Bias** | Chi-Square ($\chi^2$) | $\chi^2 = 57.891, p < 0.0001$ | $74.87\%$ preference for Markdown syntax over plain text in human-tied decisions. |
| **Inter-Judge Agreement** | Inter-Model $\kappa$ | $\kappa = 0.3690$ ($N=200$) | Substantial divergence between proprietary (`gpt-4o-mini`) and open-source (`llama3`). |
| **Calibration Holdout** | 5-Fold Cross-Val | $r = -0.0015, p = 0.9538$ | Completely eliminates length correlation on unseen 20% test holdout folds. |
| **Multi-Testing Hygiene** | Benjamini-Hochberg | FDR $lpha = 0.05$ | Prevents false-positive claims across 8 prompt domains ($p_{\text{adj}} = 0.0547$). |

---

## 🛠️ Tech Stack & Decoupled Architecture

### Frontend Workspace
- **Framework & Build**: React 18, TypeScript 5, Vite 6
- **Styling**: Tailwind CSS v4, Lucide React Icons
- **Data Visualization**: Recharts (Responsive SVG Bar, Scatter & Trend Charts)
- **API Client**: Axios (with custom error handling and SSE hooks)

### Backend & Machine Learning Engine
- **Framework**: FastAPI 0.111+, Uvicorn (ASGI Server)
- **ORM & Database**: SQLAlchemy 2.0+, PostgreSQL (`psycopg2-binary`)
- **Econometrics & Science**: SciPy, Statsmodels, scikit-learn, Pandas, NumPy
- **Testing Suite**: PyTest 9.0+, FastAPI TestClient

```
                                  ┌────────────────────────┐
                                  │   React 18 / Vite UI   │
                                  │  (Dashboard & Charts)  │
                                  └───────────┬────────────┘
                                              │ REST API & SSE (JSON)
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
                                  └───────────┴────────────┘
```

---

## ⚡ Setup & Installation Guide

### Prerequisites
- **Python**: Version `3.10+` (Python `3.11` recommended)
- **Node.js**: Version `18+` & `npm`
- **PostgreSQL**: Optional (automatic fallback database connection included)

---

### 1. Backend Setup & Server Launch

```bash
# Navigate to backend or root directory
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

# Install frozen requirements
pip install -r requirements.txt

# Configure environment variables (.env file in root)
# OPENAI_API_KEY=your_openai_api_key_here

# Launch FastAPI server
uvicorn main:app --reload --port 8000
```

Backend API server will start at `http://localhost:8000`. Interactive OpenAPI docs available at `http://localhost:8000/docs`.

---

### 2. Frontend Setup & Dev Server Launch

```bash
# Navigate to frontend directory
cd frontend

# Install Node dependencies
npm install

# Verify zero TypeScript or Vite build errors
npm run build

# Start Vite local development server
npm run dev
```

Frontend application will launch at `http://localhost:5173`.

---

### 3. Running Verification Test Suite

```bash
# Run backend pytest suite (100% passing tests)
.venv\Scripts\python.exe -m pytest -v
```

---

## 📄 License & Academic Attribution

This software is released under the **MIT License**.  
Developed for the **Master 2 Intelligent Processing Systems (IPS)** thesis at Université François-Rabelais / Master's Program.
