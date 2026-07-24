# 🎓 Master's Thesis Defense Presentation Deck
**Candidate:** Ahmed El Battah  
**Degree:** Master 2 Intelligent Processing Systems (IPS) / Data Science & AI  
**Project:** JudgeLab: LLM-as-a-Judge Reliability Lab — Measuring and Mitigating Biases in Automatic Evaluation of Generated Responses  

---

## 📌 SLIDE 3: Research Questions & Experimental Design

### 📐 Visual Layout & Component Blueprint
* **Header Banner:** Dark slate background with teal accent border. Title on left; "Methodological Framework" badge on right.
* **Layout Structure:** 4-Card Grid Matrix (2x2 Grid) with high-contrast typography, mathematical formulas in callouts, and key empirical metrics highlighted in bold teal/burgundy accent badges.
  * **Card 1 (Top-Left):** *Core Alignment & Stochastic Variance (RQ1 - RQ2)*
  * **Card 2 (Top-Right):** *Systemic Evaluative Biases (RQ3 - RQ5)*
  * **Card 3 (Bottom-Left):** *Inter-Judge & Cross-Model Divergence (RQ6)*
  * **Card 4 (Bottom-Right):** *Econometric Mitigation & Active Calibration (RQ7)*

---

### 🖼️ Slide 3 Content Markup

```markdown
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ SLIDE 3: Research Questions & Experimental Design Framework                             │
└───────────────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────┐ ┌──────────────────────────────────────────────────┐
│ 🔹 CARD 1: Alignment & Stochastic Stability     │ │ 🔹 CARD 2: Evaluative Bias Quantifications       │
│                                                  │ │                                                  │
│ • RQ1: Human Preference Alignment                │ │ • RQ3: Position Order Bias                       │
│   - Metric: Cohen's Kappa (κ = 0.4360, 72.68% acc) │ │   - Test: Chi-Square (χ² = 4.1738, p = 0.0411)   │
│   - Baseline agreement on N=1,530 MT-Bench pairs.│ │   - Significant systematic preference for Pos B. │
│                                                  │ │ • RQ4: Verbosity Bias (Length Preference)       │
│ • RQ2: Zero-Temperature Stochastic Variance      │ │   - Model: OLS Slope β = +0.000832 (p < 0.0001)  │
│   - Finding: 8.93% Empirical Flip Rate (T=0.0)   │ │   - Each +100 words yields +8.32% win rate boost.│
│   - N=150 live API trials proves GPU-kernel non- │ │ • RQ5: Structural Format Syntax Bias             │
│     determinism even at zero sampling temp.      │ │   - Test: Chi-Square (χ² = 57.891, p < 0.0001)   │
│                                                  │ │   - 84.87% Markdown preference on human ties.    │
└──────────────────────────────────────────────────┘ └──────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────┐ ┌──────────────────────────────────────────────────┐
│ 🔹 CARD 3: Inter-Judge Cross-Model Divergence    │ │ 🔹 CARD 4: Econometric Mitigation & Calibration  │
│                                                  │ │                                                  │
│ • RQ6: Multi-Model Inter-Judge Consensus         │ │ • RQ7: Out-of-Sample Length Neutralization       │
│   - Metric: Inter-Judge Kappa (κ = 0.3690, N=200)│ │   - Pipeline: 5-Fold Cross-Validation OLS        │
│   - Substantial divergence between proprietary   │ │   - Holdout Result: Residual r = -0.001481       │
│     evaluators (gpt-4o-mini) and open-source      │ │     (p = 0.9538, complete length neutrality)    │
│     models (llama3).                             │ │ • Bradley-Terry Latent Quality Modeling (θ)    │
│   - Multi-Testing Hygiene: Benjamini-Hochberg    │ │   - Solves latent log-likelihood ranking across  │
│     FDR correction (α = 0.05, p_adj = 0.054661). │ │     OpenAI, Anthropic & Open-Source models.      │
└──────────────────────────────────────────────────┘ └──────────────────────────────────────────────────┘
```

---

### 🎙️ Slide 3 Talking Points & Speaker Notes (For Jury Defense)

> *"Monsieur le Président, membres du Jury,*
>
> *Slide 3 presents the core scientific architecture of our thesis, structured around seven precise Research Questions (RQ1 through RQ7) designed to rigorously evaluate and calibrate Large Language Models as automated evaluators.*
>
> *First, regarding **Human Alignment (RQ1)**, our baseline benchmark of 1,530 MT-Bench pairwise matchups demonstrates a Cohen’s Kappa of $\kappa = 0.4360$, reflecting moderate agreement with expert human judges. However, when examining **Stochastic Consistency (RQ2)**, our empirical testing yields a key finding: even under strict zero-temperature settings ($T=0.0$), repeated live API trials reveal an **8.93% stochastic flip rate** ($91.07\%$ consensus). This proves empirically that API-level floating-point non-determinism introduces inherent variance in automated LLM scoring.*
>
> *Second, we quantify three distinct structural biases:*
> 1. **Position Bias (RQ3):** Chi-Square testing confirms a statistically significant preference for Candidate B ($\chi^2 = 4.1738, p = 0.0411$).
> 2. **Verbosity Bias (RQ4):** Our econometric regression demonstrates a highly significant positive slope ($\beta = +0.000832, p = 4.15 \times 10^{-31}$), indicating that an additional 100 words inflates candidate win probability by $+8.32$ percentage points, regardless of factual accuracy.
> 3. **Format Bias (RQ5):** On human ties, the judge selects Markdown-formatted responses over plain text in **84.87%** of cases ($\chi^2 = 57.891, p < 0.0001$).
>
> *Finally, to address **Inter-Judge Divergence (RQ6)**—where proprietary and open-source evaluators yield only $\kappa = 0.3690$ agreement—we introduce our primary scientific contribution in **RQ7**: an out-of-sample econometric neutralization pipeline. Using 5-Fold Cross-Validation, we show that residualizing scores against length achieves a holdout residual correlation of $r = -0.001481$ ($p = 0.9538$), completely neutralizing verbosity bias on unseen test sets while preserving latent Bradley-Terry quality parameters ($\theta$)."*

---

## 📌 SLIDE 4: Full-Stack System Architecture

### 📐 Visual Layout & Component Blueprint
* **Header Banner:** Dark slate background with teal accent border. Title on left; "Enterprise Software Architecture" badge on right.
* **Layout Structure:** 3-Tier Layered Stack Diagram (Top-to-Bottom Data Flow) with explicit directional arrow connectors, API endpoint specs, and component responsibilities.
  * **Top Box (Presentation Layer):** React 18, Vite 6, Tailwind CSS, Recharts Telemetry (`LiveLabPage`, `QualitativeExplorerPage`, `CalibratedLeaderboardTable`).
  * **Middle Box (API & Analytics Engine):** FastAPI Asynchronous REST Server (`main.py`, `judge_engine.py`, `calculate_neutralized_scores.py`, `analyze_consistency.py`).
  * **Bottom Box (Persistence & Asset Storage):** PostgreSQL Database (`models.py`, `database.py`) & Structured File Pipelines (`thesis_assets/`, `qualitative_data/`).

---

### 🖼️ Slide 4 Content Markup

```markdown
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ SLIDE 4: Full-Stack System Architecture & Production Engineering Pipeline               │
└───────────────────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────────────────────────────┐
  │ 🎨 PRESENTATION LAYER (React 18 + Vite 6 + Tailwind CSS)                             │
  │                                                                                      │
  │  • Interactive Dashboard & Real-Time Telemetry Views:                                │
  │    - LeaderboardPage (Calibrated Rankings & Tier Badges)                             │
  │    - DiagnosticsPage (Recharts SVG Bias Breakdown: Position, Format, Verbosity)      │
  │    - QualitativeExplorerPage (Strata Commentary & Token-Level Text Highlighting)     │
  │    - LiveLabPage (Real-Time G-EVAL Evaluation Sandbox & Prompt Injection Testing)     │
  └───────────────────────────────────────┬──────────────────────────────────────────────┘
                                          │  REST API (JSON over HTTP / Axios Client)
                                          ▼
  ┌──────────────────────────────────────────────────────────────────────────────────────┐
  │ ⚙️ APPLICATION & ANALYTICS ENGINE (FastAPI + Asynchronous Python 3.11)               │
  │                                                                                      │
  │  • API Routers & Pure Engine Modules:                                                │
  │    - main.py (GET /api/stats/bias, GET /api/leaderboard, POST /api/evaluate)         │
  │    - judge_engine.py (Decoupled G-EVAL Parser, Multi-Turn Prompt Builder, OpenAI/Ollama)│
  │    - calculate_neutralized_scores.py (OLS 5-Fold Cross-Validation Neutralizer)       │
  │    - analyze_consistency.py (Inter-Judge Kappa & Benjamini-Hochberg FDR Corrector)   │
  └───────────────────────────────────────┬──────────────────────────────────────────────┘
                                          │  SQLAlchemy ORM (Connection Pool / pre-ping)
                                          ▼
  ┌──────────────────────────────────────────────────────────────────────────────────────┐
  │ 🗄️ PERSISTENCE & ASSET PIPELINE (PostgreSQL + Local File Storage)                    │
  │                                                                                      │
  │  • PostgreSQL Relational Schemas (models.py):                                        │
  │    - Prompts (id, text, category) ──1:N──> Answers (id, text, word_count, format_type) │
  │    - HumanPreferences (id, answer_a_id, answer_b_id, winner_id)                      │
  │    - JudgeDecisions (id, position_a_id, winner_id, reasoning_text)                   │
  │  • Static File & Graphics Pipelines:                                                 │
  │    - thesis_assets/ (High-Res Publication PNG Figures @ 300 DPI)                     │
  │    - qualitative_data/ (Strata CSV Datasets & Empirical Trial Outputs)                │
  └──────────────────────────────────────────────────────────────────────────────────────┘
```

---

### 🎙️ Slide 4 Talking Points & Speaker Notes (For Jury Defense)

> *"Turning to Slide 4, I will present the software engineering architecture of **JudgeLab**, designed to adhere to strict enterprise separation of concerns, decoupling presentation logic from backend econometric computation and storage.*
>
> *1. **Presentation Layer:** The user interface is built on **React 18** bundled with **Vite 6** and **Tailwind CSS**. It incorporates four specialized research pages: the *Leaderboard Page* displaying calibrated model tiers, the *Diagnostics Page* rendering interactive SVG bias telemetry via **Recharts**, the *Qualitative Explorer* with regex token highlighting for G-EVAL reasoning, and the *Live Lab Sandbox* enabling real-time judge execution and prompt injection testing.*
>
> *2. **Application & Analytics Engine:** The backend is powered by an asynchronous **FastAPI** REST API. It is decoupled into specialized modules: `judge_engine.py` handles pure G-EVAL prompt construction and regex verdict parsing across OpenAI (`gpt-4o-mini`) and local Ollama (`llama3`) endpoints; `calculate_neutralized_scores.py` computes out-of-sample 5-Fold Cross-Validation OLS length adjustments; and `analyze_consistency.py` enforces Benjamini-Hochberg FDR correction across multi-domain testing.*
>
> *3. **Persistence & Asset Pipeline:** At the data tier, a **PostgreSQL** database managed via **SQLAlchemy ORM** tracks 1,530 benchmark matchups across normalized relational schemas (`Prompts`, `Answers`, `HumanPreferences`, `JudgeDecisions`). This is supplemented by an automated asset pipeline that exports publication-ready 300 DPI graphics directly into `thesis_assets/` and structured trial CSVs into `qualitative_data/`.*
>
> *In summary, JudgeLab is not merely a script or wrapper, but a full-stack, end-to-end scientific platform engineered to guarantee reproducibility, auditability, and real-time evaluation calibration."*
