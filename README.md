# LLM-as-a-Judge Reliability Lab

This repository contains a controlled, provenance-preserving study of pairwise
LLM judgments. The final scientific pages are `/synthesis` and
`/controlled-results`; `/` opens the historical exploratory Leaderboard.
Live Evaluation is a separate manual sandbox and remains behind its explicit
server-side provider-execution gate.

## Current corrected controlled science

The current authority is the verified source-corrected full-population analysis
[`evidence/remediation/source_corrected_complete_case_full_population_analysis_v2.json`](evidence/remediation/source_corrected_complete_case_full_population_analysis_v2.json)
(deterministic analysis-content hash `ace75cfb15412c2070b848f048ad419ae70d46162c7b66d52ee4302432031d97`; file SHA-256 `85b36f2320a91fc590014566ded1c6203a17948ccfcd3a4b8558de479cb3b49b`, recorded in the corrected package manifest).
The API selects only its pinned completed AnalysisRuns and fails closed if any
is absent or incompatible. Phase 11, `research_release_v2`,
`research_release_v3`, and historical/provisional remediation evidence remain
immutable audit records.

| RQ | Current authoritative result |
| --- | --- |
| RQ1 — Human Alignment | 457/772 = **59.20%** agreement with human preference reference labels (95% CI 55.70–62.69%); Cohen's kappa **0.3230** (95% CI 0.2698–0.3758). |
| RQ2 — Stochastic Consistency | Fixed-temperature strict complete-repetition consistency: 7,119/7,375 = **96.53%** across 1,475 strict-valid cells (1,599/1,600 physical complete cells). Conditional sensitivity: **96.31%**, N=1,585. |
| RQ3 — Position Sensitivity | **17.49%** decisive flip rate (96/549) after canonical answer-identity remapping; all-paired disagreement 193/759 = 25.43%. |
| RQ4 — Controlled Redundant-Length Effect | **0/682 = 0.00%** stable controlled redundant-text variant wins. This is the narrow frozen estimator `variant_outcome == "VARIANT"` after valid/stable pair requirements, not a broad verbosity claim. |
| RQ5 — Controlled Presentation-Format Effect | **0/716 = 0.00%** stable controlled presentation/list-prefix variant wins under the same narrow estimator, not a general formatting claim. |
| RQ6 — Counterbalanced Matched Source-Family Preference | 81/159 = **50.94%** (95% CI 42.77–58.49%; coverage 33.13%); the association has substantial judge-level heterogeneity and is not causal self-bias evidence. |
| RQ7 — Mitigation Trade-off | **PRIMARY DUAL_SWAP:** 405/597 = 67.84% to 409/597 = 68.51%, **+0.67 pp** (95% CI −0.17 to +1.68 pp), with coverage 96.87% to 75.84% (−21.03 pp): a small uncertain change plus substantial coverage loss. **SECONDARY Multi-Judge:** 808/1,125 = 71.82% vs 66.80% equal-weight comparator, **+5.02 pp** (95% CI +4.16 to +5.89 pp), 69.83% coverage of 1,611 planned pairs. |

DUAL_SWAP and Multi-Judge have different frozen units, comparators, and
estimands; direct superiority comparison is **not defensible**. Human
preference labels are reference labels, not ground truth.

## Dataset provenance and correction

The upstream dataset is **LMSYS MT-Bench Human Judgments**
(`lmsys/mt_bench_human_judgments`), associated with Zheng et al. (2023),
*Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena*
([arXiv:2306.05685](https://arxiv.org/abs/2306.05685)). The dataset license is
**CC BY 4.0**; this is distinct from the FastChat code license, **Apache-2.0**.

All 3,355/3,355 local raw human rows matched upstream. Source-text
reconciliation resolved 1,568/1,568 controlled records: 1,070
`SOURCE_EXACT`, 498 `SOURCE_CORRECTION_REQUIRED`, and 0 unresolved. Historical
DB ingestion had selected answers by insertion order, causing source-text
mismatches for those 498 controlled reference records; the upstream human
judgment dataset was not corrupted. Exact source responses were reconciled
deterministically, affected evaluations were rerun additively, and historical
evidence was retained unchanged.

Fourteen terminal Claude observations remained unavailable after bounded
recovery. Provider response identifiers were retained, but raw rejected
response bodies were not persisted, preventing scientifically defensible
offline re-parsing. The missing observations are judge-specific and
concentrated in a small subset of questions, turns, and categories. Analyses
therefore use explicitly reported complete-case populations, without claiming
MCAR or MAR.

## Reproduce and verify

### Normal reproducibility workflow

This workflow starts from an empty PostgreSQL database and never relies on the
historical working database or answer insertion order.

1. Create a virtual environment and install `requirements.txt`.
2. Set a local PostgreSQL `DATABASE_URL` in an ignored `.env` file.
3. Apply the checked-in schema migrations.
4. Build the canonical source-correct dataset from committed raw and canonical
   data.
5. Create a provider-free controlled evaluation plan, or use the separately
   authorized execution workflow when collecting new evidence.
6. Verify frozen corrected analysis outputs.
7. Run the complete reproducibility verifier, including a disposable empty-DB
   reconstruction when PostgreSQL is available.

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts\build_dataset.py
.\.venv\Scripts\python.exe scripts\run_evaluation.py --limit 80
.\.venv\Scripts\python.exe scripts\run_analysis.py
.\.venv\Scripts\python.exe scripts\verify_reproducibility.py --fresh-empty-db
```

`scripts/run_evaluation.py` is deliberately planning-only and makes zero
provider calls. Real evaluation remains separately authorized and guarded; it
is not required to verify the frozen final science.

Canonical inputs are:

- raw snapshot: `data/human_judgment.jsonl` (3,355 verified rows);
- canonical study manifest:
  `data/canonical/source_corrected_study_v1.json`;
- data-layout/provenance note: `data/metadata/CANONICAL_SOURCE_DATA.md`.

The canonical study covers **80 distinct MT-Bench questions** (preserved
upstream question IDs 81–160), represented by **160 turn-level prompt
records**: one record for each of the two MT-Bench turns per question.

### Historical correction and audit material

Historical databases, remediation/recovery ledgers, Phase 11, releases v2/v3,
and pre-correction analyses remain preserved for audit. They are not inputs to
the normal workflow above. Historical-only reconstruction helpers live under
`tools/historical/`; package verifiers remain alongside their frozen packages.

### Current code layout

`backend/main.py` is the FastAPI entrypoint. Its current domain packages are
`core/`, `data/`, `evaluation/`, `analysis/`, `experiments/`, `multijudge/`,
`historical/`, and `release/`. The public provider-free commands are
`scripts/build_dataset.py`, `scripts/run_evaluation.py`,
`scripts/run_analysis.py`, and `scripts/verify_reproducibility.py`.

The two root compatibility modules, `backend/database.py` and
`backend/controlled_models.py`, remain only for immutable frozen-package
verifiers that import those historical module names. They are not a second
runtime implementation.

### Frozen-release verification

Restore the additive `research_release_v4` snapshot when verifying the full
frozen database release. The normal dashboard path does not make provider calls.

```powershell
.\.venv\Scripts\python.exe evidence/final/phase11/VERIFY_PACKAGE.py
.\.venv\Scripts\python.exe evidence/final/research_release_v2/VERIFY_RELEASE.py
.\.venv\Scripts\python.exe evidence/final/multijudge_consensus_v1/VERIFY_PACKAGE.py
.\.venv\Scripts\python.exe evidence/final/research_release_v3/VERIFY_RELEASE.py
.\.venv\Scripts\python.exe evidence/final/controlled_source_text_corrected_v1/VERIFY_PACKAGE.py
.\.venv\Scripts\python.exe evidence/final/research_release_v4/VERIFY_RELEASE.py
```

The immutable Phase 11 root digest remains:

```text
f1a1d6ffcb6f6fd5a5dd48f7b51a731d6b765a68ff76501bf6c0ef356e53ce13
```

For the technical/scientific record, see
[`PROJECT_FINAL_TECHNICAL_AND_SCIENTIFIC_REPORT.md`](PROJECT_FINAL_TECHNICAL_AND_SCIENTIFIC_REPORT.md).
