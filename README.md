# LLM-as-a-Judge Reliability Lab

> Measuring and Mitigating Biases in Automatic Evaluation of Generated Responses

LLM-as-a-Judge Reliability Lab is a Master's applied-research project about the reliability of large language models used to evaluate generated answers. Its organizing question is how human agreement, stability, and mitigation coverage jointly describe an LLM judge as a measurement instrument.

This is not merely a web application that calls model APIs. The project combines a controlled benchmark, provenance-preserving experiment records, quantitative analysis with uncertainty estimates, frozen evidence releases, and a research dashboard. The final scientific results are source-corrected, pinned to specific completed analysis records, and can be verified without making provider calls.

## Three main research questions

| Main question | Internal analyses | Focus and official finding |
| --- | --- | --- |
| **1. Human Agreement** | RQ1 | Agreement with human preference reference labels: **457/772 = 59.20%**; Cohen's κ **0.3230**. The labels are comparison references, not absolute ground truth. |
| **2. Stability** | RQ2 and RQ3, separately | RQ2 fixed-condition repeatability: **96.53%**. RQ3 decisive mapped answer-order flips: **96/549 = 17.49%**. Repeatability measures neither accuracy nor robustness to order inversion. |
| **3. Mitigation** | RQ7 Primary / DUAL_SWAP | Matched agreement **67.84% → 68.51%**, **+0.67 pp** (official 95% CI **−0.17 to +1.68 pp**); coverage **96.87% → 75.84%**, **−21.03 pp**. The agreement change is small and uncertain while coverage falls substantially. |

High fixed-condition repeatability does not imply strong agreement with human preference reference labels or stability under answer-order inversion. The study's contribution is an integrated reliability-measurement and reproducibility framework, including the agreement–coverage trade-off of mitigation. It does not claim to have invented LLM-as-a-Judge, position or verbosity bias, consensus judging, or presentation-consistency filtering.

### Internal and supporting analyses

| RQ | Final scope |
| --- | --- |
| **RQ1 — Human alignment** | Agreement between LLM judgments and human preference reference labels. The labels are not treated as absolute ground truth. |
| **RQ2 — Repeatability** | Fixed-condition consistency when the same judge evaluates the same pair repeatedly. This is not a general temperature-effects study. |
| **RQ3 — Position sensitivity** | Change in the mapped decision when the same answers are shown as A/B and B/A. |
| **RQ4 — Secondary controlled analysis** | Exact duplicated-text treatment under a narrow design; not a general claim about verbosity bias. |
| **RQ5 — Secondary controlled analysis** | Content-equivalent list-prefix treatment; not a general claim about presentation bias. |
| **RQ6 — Exploratory source-family association** | Counterbalanced association between a judge and answer-source family; not proof of causal self-preference. |
| **RQ7 — Mitigation** | DUAL_SWAP is the main analysis; Multi-Judge consensus is secondary/exploratory and positive against its own equal-weight individual comparator. Their estimands and populations differ, so direct superiority is not assessed. |

## Research contribution

The project provides a controlled, reproducible framework for pairwise LLM judging. It preserves dataset, prompt, answer, model, configuration, presentation, pass, attempt, and analysis provenance; measures human alignment and two distinct forms of stability; reports mitigation agreement together with coverage; and presents the resulting evidence in a research dashboard.

The current authority is the **source-corrected full-population analysis**. Historical evidence remains available for audit, but it is not substituted for the current final results.

The corrected analysis artifact retains `promotion_status: "NOT_PROMOTED"` as
immutable remediation-stage history. Current authority is established later by
the release-v4 manifest and the eight pinned completed AnalysisRuns, which the
backend selects by identity and provenance contract; the historical field is
not the current promotion decision.

## Dataset

The canonical study is `source-corrected-controlled-study-v1`, built from the LMSYS MT-Bench Human Judgments source snapshot.

| Item | Verified value |
| --- | ---: |
| Controlled source records | 1,568 |
| Source exact | 1,070 |
| Source correction required | 498 |
| Unresolved records | 0 |
| Distinct MT-Bench questions | 80 (IDs 81–160) |
| Turn-level prompt records | 160 (80 turn 1 + 80 turn 2) |

The distinction matters: the study contains **80 benchmark questions**, each represented by two MT-Bench turns, rather than 160 distinct questions. The canonical manifest, raw snapshot, and provenance note are under `data/`.

## Experimental design

The framework evaluates answer pairs with structured LLM judgments. It includes repeated fixed-condition evaluations, counterbalanced A/B ↔ B/A presentation, deterministic redundant-text and format-only variants, source-family counterbalancing, and mitigation protocols. Ties, provider failures, invalid responses, missing observations, and incomplete paired units are retained as explicit operational outcomes and are handled by the estimator-specific inclusion rules.

The exact judge identifiers are `gpt-4o-mini`, `anthropic/claude-3-haiku`, `deepseek/deepseek-chat`, and `meta-llama/llama-3.3-70b-instruct`. These judge models are distinct from the historical models that produced the candidate answers. The [methodology record](docs/STUDY_METHODOLOGY.md) documents the LMSYS human-label linkage by question, turn, source model, and answer hash; A/B/TIE mapping and swapped-order remapping; prompt/JSON schema and parser; inference settings, retries, routing, seeds, and estimator-specific eligibility. Fourteen terminal Claude observations remained unavailable after bounded recovery; they were neither fabricated nor imputed, and no MCAR or MAR assumption is made.

## Final results

These are the authoritative results from the verified source-corrected full-population artifact.

| RQ | Primary estimand / population | Result | Interpretation |
| --- | --- | --- | --- |
| RQ1 | Human-reference agreement, N=772 | 457/772 = **59.20%**; Cohen's κ = **0.3230** | 95% CI: 55.70–62.69% for agreement; 0.2698–0.3758 for κ. |
| RQ2 | Strict complete-repetition consistency, N=1,475 cells | **96.53%** | Fixed-condition repeatability; conditional sensitivity is 96.31%, N=1,585. |
| RQ3 | Decisive mapped-original swap pairs, N=549 | 96/549 = **17.49%** flips | All-paired disagreement is 193/759 = 25.43%. |
| RQ4 | Stable valid redundant-text pairs, N=682 | 0/682 = **0.00%** variant wins | A narrow duplicate-text result, not a universal verbosity finding. |
| RQ5 | Stable valid presentation/list-prefix pairs, N=716 | 0/716 = **0.00%** variant wins | A narrow format-treatment result, not a universal formatting finding. |
| RQ6 | Counterbalanced stable decisive units, N=159 | 81/159 = **50.94%** | 95% CI: 42.77–58.49%; coverage is 159/480 = 33.13%; associational only. |
| RQ7 primary | DUAL_SWAP matched retained decisions, N=597 | 67.84% → 68.51%; **+0.67 pp** | 95% CI: −0.17 to +1.68 pp; coverage falls from 96.87% to 75.84%. |
| RQ7 secondary | Multi-Judge retained consensus pairs, N=1,125 of 1,611 planned | 71.82% vs 66.80%; **+5.02 pp** | 95% CI: +4.16 to +5.89 pp against its equal-weight individual-judge comparator. |

For full metric definitions, strata, and operational accounting, consult [the technical and scientific record](PROJECT_FINAL_TECHNICAL_AND_SCIENTIFIC_REPORT.md) and the frozen evidence.

### Statistical-dependence sensitivity

Observations from the same original MT-Bench question may be correlated. A separate deterministic **10,000-replicate question-clustered bootstrap** (seed `20260912`) therefore resampled original question IDs while keeping their turns, judges, repetitions, swaps, variants, and matched observations together. All substantive conclusions remained unchanged. This is a robustness check and **does not replace any frozen official confidence interval**. For RQ7 Primary coverage delta, its **−24.62 to −17.64 pp** interval is sensitivity-analysis evidence only; the frozen result had no official CI for that delta. See the [validation record](evidence/validation/question_clustered_bootstrap_sensitivity_v1.md).

## Interpretation boundaries and limitations

- Human labels are preference reference labels, not objective ground truth.
- RQ4 and RQ5 estimate only their documented controlled treatments.
- RQ6 is an association; residual source and answer-quality confounding prevent a causal self-bias conclusion.
- RQ7 DUAL_SWAP has a small, uncertain agreement difference and a substantial coverage trade-off. Multi-Judge is evaluated against its own retained-pair comparator, not against DUAL_SWAP.
- Provider-specific missing observations are reported through the complete-case populations rather than silently removed.
- Official bootstrap intervals apply to the logical units specified by each estimator. The separate question-clustered sensitivity addresses possible within-question dependence without changing those intervals.
- The final analysis and evidence are reproducible from the released database and frozen artifacts. Exact historical provider-response replay is not guaranteed where provider-side determinism, seed behavior, or immutable provider-revision metadata was unavailable or not durably exposed.

## Architecture

```text
React / Vite frontend
        ↓ REST
FastAPI API (`backend/main.py`)
        ↓
PostgreSQL experiment and provenance database
        ↓
analysis · evaluation · controlled experiments · multi-judge modules
        ↓
canonical data, frozen evidence, and reproducibility releases
```

The backend is organized by responsibility:

- `backend/core/` — database, ORM, model registry, and pinned final evidence.
- `backend/data/` — canonical source-text validation and fresh dataset construction.
- `backend/evaluation/` — protocols, planning, provider routing, execution, and persistence.
- `backend/analysis/` — estimators and source-corrected full-population analysis.
- `backend/experiments/` — counterbalanced source-family experiment support.
- `backend/multijudge/` — secondary multi-judge consensus protocol.
- `backend/historical/` and `backend/release/` — preserved lineage and release verification.

## Application pages

| Route | Evidence class / purpose |
| --- | --- |
| `/leaderboard` | **Historical/exploratory** telemetry. This remains the current default landing route. |
| `/synthesis` | **Authoritative** executive synthesis of final controlled science. |
| `/controlled-results` | **Authoritative** detailed RQ1–RQ7 controlled evidence. |
| `/diagnostics` | **Historical/exploratory** diagnostics. |
| `/qualitative-explorer` | **Historical/exploratory** provenance-gated qualitative inspection. |
| `/live-lab` | **Manual sandbox**; separate from frozen final evidence. |

The authoritative pages use `/api/controlled/results`, which selects only pinned, compatible corrected analysis records and fails closed rather than falling back to legacy or live results.

## Prerequisites

- Git, to clone the repository.
- Python and `venv` compatible with the pinned packages in `requirements.txt`.
- PostgreSQL for application use, canonical dataset construction, and database recomputation.
- Node.js and npm for the frontend.

The repository does not declare a single minimum Python, Node.js, or PostgreSQL version. Use versions compatible with the pinned dependencies and local PostgreSQL tooling.

### Verified development / reproducibility environment

The current local verification environment used Python 3.11.4, Node.js v22.18.0, and npm 10.9.3. PostgreSQL client binaries are resolved portably by the release tooling; they need not be on `PATH` when a discoverable local PostgreSQL installation is available. These are tested versions, not minimum compatibility claims.

## Installation

```bash
git clone https://github.com/ELBATTAHAHMED/LLM-Judge-Lab.git
cd LLM-Judge-Lab

python -m venv .venv
```

Activate the environment:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

Install the pinned Python dependencies and frontend dependencies:

```bash
python -m pip install -r requirements.txt
npm install --prefix frontend
```

## Environment configuration

Copy `.env.example` to `.env` and configure the database connection. Do not commit `.env`.

```bash
cp .env.example .env
```

On Windows, create the copy with your preferred file-management command. The relevant variables are:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Application PostgreSQL connection string. |
| `OPENAI_API_KEY` | Optional; required only for applicable Live Evaluation provider calls. |
| `OPENROUTER_API_KEY` | Optional; required only for applicable Live Evaluation provider calls. |
| `ENABLE_LIVE_SANDBOX_PROVIDER_CALLS` | Manual provider-call gate; `false` by default. |
| `JUDGELAB_CORS_ORIGINS` | Allowed frontend origins; the example permits local Vite origins. |
| `OLLAMA_BASE_URL` | Optional local-provider base URL. |

For application configuration, normal `python-dotenv` behavior applies: process environment values take precedence over `.env`, which takes precedence over code defaults. Credentials stay server-side; never put them in frontend variables or commit them.

### Alembic connection note

Alembic reads **`ALEMBIC_DATABASE_URL`** from the process environment; it does not load `.env`. Before applying migrations, export `ALEMBIC_DATABASE_URL` with the same PostgreSQL connection string as `DATABASE_URL`.

```powershell
# PowerShell: set this to the same PostgreSQL URL used in .env
$env:ALEMBIC_DATABASE_URL = 'postgresql://user:password@host:5432/database'
python -m alembic upgrade head
```

```bash
# macOS / Linux
ALEMBIC_DATABASE_URL='postgresql://user:password@host:5432/database' python -m alembic upgrade head
```

## Canonical dataset build

After migrations, run:

```bash
python scripts/build_dataset.py
```

This validates the committed raw source and canonical manifest, then builds the canonical source-correct dataset into an **empty** database. It fails if the target database already contains prompts.

## Provider-free experiment planning

```bash
python scripts/run_evaluation.py --limit 80
```

This command reads canonical pair records and emits a deterministic evaluation plan. It is planning-only and reports `provider_calls: 0`; it does not rerun paid experiments.

## Final analysis

Two provider-free commands have different purposes:

### A. Verify the frozen corrected artifact

```bash
python scripts/run_analysis.py
```

This validates the canonical dataset and the authoritative frozen result values. It does not require database analysis execution.

### B. Independently recompute from PostgreSQL

```bash
python scripts/run_analysis.py --recompute-from-db
```

This recomputes the final RQ1–RQ7 results from the current or restored experimental PostgreSQL database using the authoritative estimator implementation, then compares the recomputed artifact identity with the frozen result. It makes no provider calls.

The final controlled dashboard and an independent database recomputation require the released or restored experimental PostgreSQL database. A fresh canonical build validates source data and planning; it does not reconstruct historical provider executions.

## Fresh reproducibility check

```bash
python scripts/verify_reproducibility.py --fresh-empty-db
```

This provider-free verification creates a uniquely named disposable PostgreSQL database, applies migrations, builds canonical data, plans a small evaluation, checks source hashes, and removes the temporary database afterward. It does not re-execute paid model evaluations.

## Running the application

Start the backend from the repository root:

```bash
python -m uvicorn backend.main:app
```

Uvicorn uses its local development defaults (`127.0.0.1:8000`), so no host or
port flags are required. If port 8000 is already in use, stop the existing
local backend process before starting another one.

Start the frontend in another terminal:

```bash
cd frontend
npm run dev
```

The backend is served on `http://127.0.0.1:8000`; Vite is configured for port `5173`. Open the frontend at `http://localhost:5173`, then use `/synthesis` or `/controlled-results` for the final research evidence.

## Live Evaluation

Live Evaluation is an optional manual/exploratory sandbox, separate from the frozen study. It can make real provider calls and may incur cost. Its operational records are retained for inspection but excluded from historical telemetry and frozen RQ1–RQ7 evidence; exact replay of a provider response is not guaranteed because provider behavior and revisions can change. It is not required for installation, reproducibility, final analysis verification, or presentation of the final RQ results.

The backend rejects manual provider transport unless `ENABLE_LIVE_SANDBOX_PROVIDER_CALLS=true` is explicitly configured. Do not enable it without appropriate provider credentials and cost controls.

Blank or whitespace-only questions and candidate answers are rejected before provider transport or persistence. Client-facing provider failures, including failed Live Ensemble members, are sanitized; raw provider exception details remain server-side.

## Testing and build checks

Run backend tests from the repository root:

```bash
python -m pytest
```

Run frontend checks from `frontend/`:

```bash
npm run test
npm run lint
npx tsc --noEmit -p tsconfig.app.json
npm run build
```

The production build writes `frontend/dist/`, which is ignored by Git.

## Reproducibility and evidence

| Item | Authoritative location / identity |
| --- | --- |
| Canonical dataset | `data/canonical/source_corrected_study_v1.json`; identity `source-corrected-controlled-study-v1`; canonical dataset SHA-256 `f4dd4b2ec9e44d61b7e963b34eba6fe796f61fbe930100f9c6fff82da6ab1209` |
| Corrected analysis | `evidence/remediation/source_corrected_complete_case_full_population_analysis_v2.json`; analysis identity `source-corrected-complete-case-full-population-analysis-v2`; content hash `ace75cfb15412c2070b848f048ad419ae70d46162c7b66d52ee4302432031d97` |
| Corrected evidence package | `evidence/final/controlled_source_text_corrected_v1/` |
| Current PostgreSQL release | `evidence/final/research_release_v4/` |

The analysis content hash identifies the deterministic analysis material; it is not a claim about the byte hash of every release file. Package manifests and their verifier scripts check file-level integrity. The frozen package verifiers also reconcile pinned records with the currently configured database; they are integrity/provenance checks, not a substitute for restoring a release dump.

Useful offline verifiers include:

```bash
python evidence/final/phase11/VERIFY_PACKAGE.py
python evidence/final/controlled_source_text_corrected_v1/VERIFY_PACKAGE.py
python evidence/final/research_release_v4/VERIFY_RELEASE.py
```

To validate the **actual release-v4 database dump** end to end, use the
provider-free supported workflow below. It verifies the dump checksum, restores
the dump into a uniquely named disposable PostgreSQL database, reconciles the
controlled API and pinned AnalysisRuns there, independently recomputes the
analysis there, and then removes only that verifier-created database. PostgreSQL
client tools are resolved from `POSTGRES_BIN`, then `PATH` (with version-agnostic
Windows discovery as a fallback).

```bash
python -m backend.release.verify_v4_api
```

## Project structure

```text
alembic/              Database migrations
backend/              FastAPI application and research modules
data/                 Raw snapshot, canonical study, and dataset metadata
evidence/             Frozen evidence packages and releases
frontend/             React/Vite dashboard
scripts/              Dataset, planning, analysis, and reproducibility entry points
tests/                Backend, integration, methodology, and reproducibility tests
tools/                Historical audit and release helpers
```

### Current reproducibility entry points

The supported provider-free workflow is intentionally small and explicit:

```bash
# Build/validate the canonical source-corrected dataset
python scripts/build_dataset.py

# Produce a provider-free controlled-evaluation plan (planning only)
python scripts/run_evaluation.py --limit 80

# Verify the frozen analysis artifact; add --recompute-from-db for an
# independent database recomputation
python scripts/run_analysis.py
python scripts/run_analysis.py --recompute-from-db

# Run the fresh-start reproducibility rehearsal
python scripts/verify_reproducibility.py --fresh-empty-db
```

These commands do not contact model providers. Provider-backed Live Evaluation
is a separate, manually authorized sandbox and is never part of the frozen
RQ1–RQ7 evidence. One-off audit and release-history utilities are retained
under `tools/historical/` and are not required to start the application.

## Security and safety

- `.env` and related local environment files are ignored by Git.
- Provider credentials are server-side configuration only.
- Manual provider execution is disabled by default.
- Frozen analysis and reproducibility verification are provider-free.
- Never commit provider keys, database credentials, or generated local database files.

## Further reading

- [Technical and scientific record](PROJECT_FINAL_TECHNICAL_AND_SCIENTIFIC_REPORT.md)
- [Canonical source-data note](data/metadata/CANONICAL_SOURCE_DATA.md)
- [Final evidence directory](evidence/final/)
