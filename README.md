# LLM-as-a-Judge Reliability Lab

[![Academic PFE](https://img.shields.io/badge/Academic%20Project-Master%20IPS%20PFE-blue.svg)](https://github.com/ELBATTAHAHMED/LLM-Judge-Lab)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19.0-61DAFB.svg?logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6.svg?logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15.0+-4169E1.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

**Author:** Ahmed El Battah  
**Degree:** Master Intelligent Processing Systems (IPS - Projet de Fin d'Études / Master's Thesis)  
**Repository:** [ELBATTAHAHMED/LLM-Judge-Lab](https://github.com/ELBATTAHAHMED/LLM-Judge-Lab)

---

## Research evidence status (August 2026)

Final controlled execution is complete: **13,400 / 13,400 units** and
**16,600 / 16,600 pass slots** are accounted, with **0 pending** units and
**7 / 7 AnalysisRuns** completed. Final findings use only `CONTROLLED`
evidence. `PILOT`, `SUPERSEDED_CONTROLLED`, `LIVE_SANDBOX`, and
`LEGACY_EXPLORATORY` records are not final scientific evidence.

The immutable reproducibility package is
[`evidence/final/phase11/`](evidence/final/phase11/). Verify it offline with
`python evidence/final/phase11/VERIFY_PACKAGE.py`. Its frozen release tag is
`phase11-final-evidence-frozen-v1`; the synchronized frontend release tag is
`phase12-final-frontend-sync-v1`.

### Final controlled research questions and results

- **RQ1 — Human Alignment:** 58.44% agreement with human preference reference
  labels; Cohen's kappa 0.3121.
- **RQ2 — Stochastic Consistency:** 96.56% consistency.
- **RQ3 — Position Sensitivity / Bias:** 16.70% paired decisive flip rate.
- **RQ4 — Controlled Redundant-Length Effect:** 0.44% redundant-variant win
  rate; this is not a broad verbosity-bias conclusion.
- **RQ5 — Controlled Presentation-Format Effect:** 1.11% format-variant win
  rate; superseded pre-fix RQ5 runs are excluded.
- **RQ6 — Matched Source-Family Preference:** **NOT ESTIMABLE** because of
  `UNBALANCED_PRESENTATION`.
- **RQ7 — BASELINE SINGLE-PASS vs DUAL_SWAP Mitigation:** agreement increased
  from 60.65% to 68.78% (+8.13 pp), while valid coverage decreased from 95.63%
  to 72.88% (-22.75 pp). This is a mitigation trade-off, not universal
  reliability improvement.

---

## 📌 Executive Summary

**JudgeLab** is a reproducible full-stack research platform for evaluating the
reliability of LLM-as-a-Judge systems in pairwise response comparison. The
final study evaluates OpenAI GPT-4o-mini, Claude 3 Haiku, DeepSeek Chat, and
Llama 3.3 70B against human preference reference labels, using frozen
controlled protocols and explicit evidence provenance.

The dashboard presents final controlled RQ1–RQ7 findings separately from
historical exploratory diagnostics. It does not convert exploratory telemetry
into final claims.

---

## 🏗 System Architecture & Technology Stack

The platform follows a decoupled, production-grade full-stack architecture:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                   React 19 + TypeScript Web Frontend                     │
│        (Vite, Tailwind CSS, Recharts Minimalist Analytics UI)            │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │ HTTP / REST API (Axios)
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         FastAPI Backend Server                           │
│        (Asynchronous API, Pydantic Validation, CORS Handler)            │
└──────────────────┬─────────────────────────────────┬─────────────────────┘
                   │                                 │
     SQLAlchemy    │                                 │ Parallel Multi-Threading
                   ▼                                 ▼
┌────────────────────────────────────┐    ┌────────────────────────────────┐
│   PostgreSQL Persistence Layer     │    │      LLM API Providers         │
│ (Prompts, Answers, Human Choices,  │    │ • OpenAI (GPT-4o-mini)         │
│  >19,000 Empirical Decision Rows)  │    │ • OpenRouter (DeepSeek/Claude) │
└────────────────────────────────────┘    │ • Local Ollama (Llama 3)       │
                                          └────────────────────────────────┘
```

### Technology Stack
- **Backend Core**: FastAPI (Asynchronous REST API framework), Pydantic v2 (Schema validation & data parsing), NumPy & SciPy (Inferential statistics & regression), scikit-learn (Cohen's Kappa & K-fold cross-validation), pandas (Dataframe aggregation).
- **Persistence Layer**: PostgreSQL database managed via SQLAlchemy ORM (Handling **19,211 historical decision rows** across 4 major model families with auto-increment sequence resynchronization).
- **Frontend Core**: React 19, TypeScript 5.0+, Vite 8, React Router DOM v7.
- **Analytics & Styling**: Recharts (Interactive SVG scatter plots, bar charts, heatmap matrices), Tailwind CSS v4 (Enterprise Bloomberg-terminal minimalist aesthetic with dark/light mode support), Lucide React (System iconography).

---

## 🔬 Mathematical Methodology & Econometric Models

JudgeLab implements advanced econometric models, inferential statistics, and real-time debiasing protocols:

### 1. Latent Quality Parameter Estimation (Bradley-Terry MLE)
Raw win rates suffer from strength-of-schedule confounding. JudgeLab fits a **Bradley-Terry Maximum Likelihood Estimation ($\theta$)** model using `scipy.optimize.minimize` (Davidson 1970 tie-formulation L-BFGS-B optimization):
$$\mathbb{P}(M_i \succ M_j) = \frac{e^{\theta_i}}{e^{\theta_i} + e^{\theta_j} + e^{\gamma + 0.5(\theta_i + \theta_j)}}$$

This produces a judge-relative pairwise ranking ($\theta$), conditional on the historical sample and available comparisons; it is not objective model merit.

### 2. Length-Neutralized Quality Calibration (5-Fold CV OLS Residual Decomposition)
To isolate genuine answer quality from length inflation, JudgeLab executes a 5-fold cross-validated **Ordinary Least Squares (OLS) regression** modeling verdict probability against word-count disparity ($\Delta W = W_A - W_B$):
$$Y_{ij} = \alpha + \beta \cdot \Delta W_{ij} + \varepsilon_{ij}$$

The out-of-sample residual $\varepsilon_{ij}$ represents the length-neutralized quality score, producing zero-centered rankings that strip verbosity inflation ($\beta$).

### 3. Controlled Dual-Pass A/B Swap Protocol
Final RQ3 measures paired decisive flip rate from matched A/B and B/A passes.
Aggregate legacy slot-win imbalance remains separate and is not a substitute
for the controlled metric.

### 4. Dynamic Self-Preference Hypothesis Testing
Evaluates model family favoritism using exact SciPy binomial testing (`binomtest`). The null hypothesis baseline ($p_0$) is dynamically computed as the judge model's baseline win rate against rival model families:
$$H_0: p_{\text{self}} \le p_{\text{rival\_baseline}} \quad \text{vs} \quad H_1: p_{\text{self}} > p_{\text{rival\_baseline}}$$

Historical source-family associations remain exploratory. Final RQ6 is
`NOT ESTIMABLE` because the controlled presentation is unbalanced; no numeric
source-family effect is claimed.

---

## 📁 Repository Directory Structure

```
LLM-Judge-Lab/
├── backend/                        # FastAPI Python Asynchronous Server & Services
│   ├── main.py                     # Main API Server & 12 REST Route Handlers
│   ├── database.py                 # SQLAlchemy Database Engine & Sequence Resync
│   ├── models.py                   # ORM Database Schemas (Prompts, Answers, Decisions)
│   ├── judge_engine.py             # Pure Evaluation Engine & Mitigation Protocols
│   ├── analyze_results.py          # Statistical Analysis & Matplotlib Visualization Engine
│   ├── analyze_consistency.py      # Multi-Turn Logical Consistency & Self-Preference Engine
│   ├── calculate_latent_quality.py # Bradley-Terry MLE Optimization Model
│   ├── calculate_neutralized_scores.py # 5-Fold CV OLS Residual Length Neutralization Model
│   ├── generate_ablation_matrix.py # Component Ablation Study Matrix Generator
│   ├── generate_perturbations.py # Counterfactual Synthetic Perturbation Engine
│   ├── stochastic_test.py          # Empirical Repeated-Run Stochastic Flip Test Runner
│   ├── ingest_data.py              # MT-Bench & Vicuna Dataset Ingestion Pipeline
│   └── verify_db.py                # Database Health & FK Integrity Audit Script
├── frontend/                       # React 19 + TypeScript + Vite Web UI
│   ├── src/
│   │   ├── api/                    # Axios API Client & Custom React Hooks
│   │   ├── components/             # Reusable UI Analytics Components & Charts
│   │   ├── context/                # ThemeContext & JudgeContext
│   │   ├── layouts/                # Dashboard Shell & Collapsible Sidebar Layout
│   │   ├── pages/                  # Leaderboard, Synthesis, Diagnostics, Explorer, LiveLab
│   │   └── index.css               # Core Tailwind CSS Styling Directives
│   ├── package.json
│   └── vite.config.ts
├── tests/                          # Automated PyTest Test Suite
│   ├── test_pipeline.py            # End-to-End Backend Test Cases (11/11 Passing)
│   └── test_api_connections.py     # Live API Connectivity Diagnostic Script
├── thesis_docs/                    # Master's Thesis Documentation & Artifacts
│   ├── thesis_chapter_5_exhibits.md# Chapter 5 Empirical Thesis Exhibits & Findings
│   └── thesis_defense_presentation_slides.md # Thesis Defense Presentation Outline
├── qualitative_data/               # Stratified Qualitative Case Buckets & Results
├── requirements.txt                # Python Dependencies
└── README.md                       # Master Thesis Project Documentation
```

---

## 🚀 Quick Start Guide

### Prerequisites
* **Python**: 3.11 or higher
* **Node.js**: v18.0 or higher (`npm`)
* **Database**: PostgreSQL (or local SQLite fallback)

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
# Database Connection (PostgreSQL)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/judgelab

# LLM Provider API Keys
OPENAI_API_KEY=your_openai_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Local Model Provider (Optional Ollama setup)
OLLAMA_BASE_URL=http://localhost:11434/v1
```

---

### Step 3: Ingest Dataset & Audit Database

```bash
# Ingest prompts, answers, and human preference data into PostgreSQL
python backend/ingest_data.py

# Verify database health and FK integrity
python backend/verify_db.py
```

---

### Step 4: Launch Backend API Server

```bash
# Start FastAPI server on http://localhost:8000
uvicorn backend.main:app --reload --port 8000
```
*Interactive Swagger API documentation is available at `http://localhost:8000/docs`.*

---

### Step 5: Launch Frontend Client

In a separate terminal window:

```bash
cd frontend
npm install
npm run dev
```
*Access the web application at `http://localhost:5173`.*

---

### Step 6: Execute PyTest Verification Suite

```bash
pytest tests/test_pipeline.py -v
```

---

## 📄 License & Citation

This project is released under the MIT License.

```bibtex
@mastersthesis{elbattah2026llmjudge,
  author       = {Ahmed El Battah},
  title        = {LLM-as-a-Judge Reliability Lab: Empirical Auditing and Active Calibration of Systematic Evaluator Biases},
  school       = {Master Intelligent Processing Systems (IPS)},
  year         = {2026},
  type         = {Projet de Fin d'\'Etudes (PFE)}
}
```
