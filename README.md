# LLM-as-a-Judge Reliability Lab

This repository contains the final controlled study and a reproducible dashboard
for auditing pairwise LLM judgments. Phase 11 remains immutable historical
evidence; the additive `research_release_v2` package pins corrected
provider-free analyses and the separately executed counterbalanced RQ6 lineage.

## Final controlled evidence

The frozen Phase 11 execution accounts for **13,400 / 13,400 controlled units**
and **16,600 / 16,600 pass slots**, with 0 pending units and 7 / 7 original
canonical `AnalysisRun` records completed. The separate final RQ6 lineage
accounts for 480 / 480 units and 960 / 960 pass slots.

| RQ | Final controlled result |
| --- | --- |
| RQ1 — Human Alignment | 58.44% agreement with human preference reference labels; Cohen's kappa 0.3121; N=770. |
| RQ2 — Stochastic Consistency | **Primary strict** complete-repetition consistency: 96.74% (95% CI 96.22–97.23%; N=1,428). Conditional returned-judgment sensitivity: 96.56% (N=1,474). No temperature comparison is estimable. |
| RQ3 — Position Sensitivity | 16.70% paired decisive flip rate; 24.87% all-paired disagreement. Reconciled decisive flips: Claude 52.25%, GPT-4o-mini 5.17%, Llama 7.79%, DeepSeek 9.15%. |
| RQ4 — Controlled Redundant-Length Effect | 0.44% redundant-variant win rate; N=685. This is a narrow redundant-text control, not a general claim about verbosity. |
| RQ5 — Controlled Presentation-Format Effect | 1.11% format-variant win rate; N=719. This applies to the implemented controlled transformation only. |
| RQ6 — Counterbalanced Matched Source-Family Preference | 50.94% stable same-family preference (95% CI 42.77–58.49%; N=159 stable decisive). No clear uniform overall preference; results vary strongly by judge. |
| RQ7 — Mitigation Trade-off | Matched retained-decision agreement: 67.66% → 68.37% (**+0.70 pp**, 95% CI 0.00–1.58; N=569); descriptive coverage: 95.63% → 72.88% (-22.75 pp). This matched comparison is not a causal treatment effect. |

Human preferences are reference labels, not ground truth. The results do not
claim a universally best judge, universal causal bias, or universal mitigation
improvement.

The original frozen RQ6 design was not estimable due to unbalanced
presentation. A separate counterbalanced RQ6 experiment was later executed and
analyzed: presentation order is controlled, but source/content-quality
confounding remains. Its 33.13% stable-decisive coverage limits conclusions to
those retained units; it is a matched source-family preference association, not
causal proof of self-bias.

## Reproducing the final dashboard

Normal application startup is read-only: it does not run schema maintenance,
experiments, or provider calls. Provider credentials are not required to
inspect the final dashboard or verify the frozen package.

```powershell
git clone https://github.com/ELBATTAHAHMED/LLM-Judge-Lab.git
cd LLM-Judge-Lab
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cd frontend
npm install
cd ..
Copy-Item .env.example .env
```

Set `DATABASE_URL` in `.env` for a local PostgreSQL database. Restore the
canonical snapshot with your matching PostgreSQL client and database name:

```powershell
& 'C:\Program Files\PostgreSQL\17\bin\pg_restore.exe' --clean --if-exists --no-owner --dbname judgelab evidence/final/research_release_v2/database/judgelab-final-research-release-v2.dump
```

Then use two terminals:

```powershell
uvicorn backend.main:app --reload --port 8000
```

```powershell
cd frontend
npm run dev
```

Open `http://localhost:5173/` (Leaderboard is the default; Controlled Experiments
is the primary navigation tab). The final scientific pages
(`/controlled-results` and `/synthesis`) use only `/api/controlled/results`,
which fail-closes to the pinned canonical AnalysisRuns rather than falling back
to legacy data. Verify the offline evidence package independently:

```powershell
python evidence/final/phase11/VERIFY_PACKAGE.py
```

```powershell
python evidence/final/research_release_v2/VERIFY_RELEASE.py
```

Expected Phase 11 root digest:

```text
f1a1d6ffcb6f6fd5a5dd48f7b51a731d6b765a68ff76501bf6c0ef356e53ce13
```

## Dataset provenance

The frozen final dataset identity is recorded in
`evidence/final/phase11/dataset/`:

- DatasetVersion: `2f8c7bba-08b1-4d8b-8b0e-b564e8a61886`
- Version/name: `controlled-final-plan-v1`
- Source name: `judgelab-canonical-human-reference`
- SHA-256: `b2fff1524b199fb2d302b7c4ebd752a9a47d32bab68a232ab06b7b1e07fa1510`
- Human preference reference-label policy: `unordered-pair-consensus-v1`
- Legacy whole-database import metadata: 1,615 human-reference pairs, 107
  prompts, and 2,139 answers.

Those legacy metadata counts are **not** the final controlled source subset.
All canonical controlled units use exactly the 80 raw prompts with IDs 81–160;
their raw-file hashes and reconciliation are recorded in
`evidence/final/research_release_v2/dataset/canonical_controlled_source_manifest.json`.
The checked-in source metadata does not verify an upstream license or
attribution, so no license claim is made here.

The checked-in raw/source files are `data/question.jsonl`,
`data/human_judgment.jsonl`, and model-answer JSONL files for Alpaca, Claude,
GPT-3.5, GPT-4, Llama, and Vicuna. The frozen lineage canonicalizes human
judgments as unordered consensus pairs, records the import filters and identity
in the DatasetVersion evidence, then materializes checksum-linked controlled
variants for RQ4 and RQ5. Final inclusion/exclusion, unit, pass, attempt, and
analysis lineage are preserved in the Phase 11 package rather than recreated at
runtime. License/attribution metadata requires external verification.

## Evidence boundaries

- `evidence/final/phase11/` is immutable and includes the offline verifier,
  manifests, database snapshot, provenance, analysis tables, and checksums.
- `evidence/final/rq6_counterbalanced/` is a separate, post-Phase-11 RQ6
  provenance addendum. It contains the deterministic selection manifest and
  references to the executed manifest, run ledger, and canonical AnalysisRun;
  it does not amend or reseal Phase 11.
- Live Evaluation remains visible as a manual demo workflow. Backend
  live-provider endpoints are disabled by default and are not part of the
  controlled study.
- The leaderboard and diagnostics are retained only as labeled historical,
  exploratory views. The retired macro benchmark and leaderboard-recalculation
  routes are not exposed by the final application.

For a concise technical and scientific record, see
[`PROJECT_FINAL_TECHNICAL_AND_SCIENTIFIC_REPORT.md`](PROJECT_FINAL_TECHNICAL_AND_SCIENTIFIC_REPORT.md).
