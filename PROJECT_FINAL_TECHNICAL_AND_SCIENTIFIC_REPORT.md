# LLM-as-a-Judge Reliability Lab: Current Technical and Scientific Record

## Scientific framing and contribution

This integrated reliability-measurement and reproducibility study is organized around **three main questions**. **Human Agreement** (RQ1) asks how often judge decisions match human preference reference labels: 457/772 = **59.20%**, with Cohen's κ = **0.3230**. **Stability** combines two separate analyses: RQ2's **96.53%** fixed-condition repeatability and RQ3's **96/549 = 17.49%** decisive mapped flips after answer-order inversion. These are distinct estimands: repeatability does not establish correctness, strong human alignment, or order robustness. **Mitigation** is primarily RQ7 DUAL_SWAP: matched agreement changed from **67.84%** to **68.51%** (**+0.67 pp**, official 95% CI **−0.17 to +1.68 pp**) while coverage changed from **96.87%** to **75.84%** (**−21.03 pp**). The agreement change is small and uncertain, and the coverage loss is substantial.

RQ4 and RQ5 remain secondary narrow controlled treatment analyses; their zero variant-win findings do not establish that generic verbosity or presentation bias is absent. RQ6 is an exploratory source-family **association**, not causal self-bias evidence. RQ7 Multi-Judge is secondary/exploratory mitigation evidence with a positive matched effect against its own equal-weight individual comparator on its own retained population. Its effect must not be directly ranked against DUAL_SWAP. The contribution is the integrated, provenance-controlled measurement and interpretation of these dimensions, not invention of LLM-as-a-Judge, known biases, consensus, or swap filtering.

## Authority and evidence boundary

The current controlled science is the source-corrected full-population analysis
`source-corrected-complete-case-full-population-analysis-v2`, frozen in
[`evidence/remediation/source_corrected_complete_case_full_population_analysis_v2.json`](evidence/remediation/source_corrected_complete_case_full_population_analysis_v2.json)
(deterministic analysis-content hash `ace75cfb15412c2070b848f048ad419ae70d46162c7b66d52ee4302432031d97`; file SHA-256 `85b36f2320a91fc590014566ded1c6203a17948ccfcd3a4b8558de479cb3b49b`, recorded in the corrected package manifest).
It selects the following authoritative completed AnalysisRuns:

| Result | AnalysisRun |
| --- | --- |
| RQ1 | `115de122-6298-4aab-a255-dd5aedf9b3cc` |
| RQ2 | `32f93918-f127-4cde-a0cd-6a73659daca7` |
| RQ3 | `63995b48-a3a6-4386-b9b2-5f8bea3adfdb` |
| RQ4 | `d8eac555-6c46-49e7-ac19-8c271e719849` |
| RQ5 | `067b3b9a-c739-41d9-8e2a-6d44478e6299` |
| RQ6 | `416edb12-b0ba-4851-9aad-6e7ad4a01529` |
| RQ7 PRIMARY — DUAL_SWAP | `c7057075-722a-4559-ac9b-d24e068d3769` |
| RQ7 SECONDARY — Multi-Judge | `feef94e7-ca66-4fdf-8cf1-a46edd6094b4` |

The backend reads these records by identity and fails closed if their complete
source-corrected provenance contract is absent. Historical Phase 11 evidence,
release v2/v3 snapshots, pre-correction analyses, and provisional Phase-E
subset runs remain preserved for audit and are not current scientific values.

The immutable source-corrected artifact retains `promotion_status:
"NOT_PROMOTED"` from its remediation-stage creation. That field records the
earlier stage rather than the current authority decision: release v4 explicitly
pins the artifact identity and the eight completed AnalysisRuns above, and the
backend fails closed unless that later contract is present. The historical
artifact is therefore preserved without being rewritten.

## Dataset provenance and source correction

The source is **LMSYS MT-Bench Human Judgments**,
`lmsys/mt_bench_human_judgments`, documented by Zheng et al. (2023), *Judging
LLM-as-a-Judge with MT-Bench and Chatbot Arena* (arXiv:2306.05685). The dataset
license is **CC BY 4.0**. It must not be conflated with the FastChat codebase,
which is licensed **Apache-2.0**.

Forensic reconciliation matched all **3,355/3,355** local raw human rows to the
upstream data. It reconciled all **1,568/1,568** controlled source records:
**1,070 SOURCE_EXACT**, **498 SOURCE_CORRECTION_REQUIRED**, and **0
UNRESOLVED**. The upstream human-judgment data was not corrupted. Instead,
historical DB ingestion selected answers by insertion order, which caused a
source-text mismatch in 498 controlled reference records. Deterministic source
reconciliation recovered the exact source responses; affected evaluations were
rerun additively, while historical evidence remained immutable.

Fourteen terminal Claude observations remained unavailable after bounded
recovery. Provider response identifiers were retained, but raw rejected
response bodies were not persisted, preventing scientifically defensible
offline re-parsing. They were neither fabricated nor imputed. The missing observations are judge-specific and
concentrated in a small subset of questions, turns, and categories. Analyses
therefore use explicitly reported complete-case populations, without claiming
MCAR or MAR.

## Corrected research results

The table retains every internal RQ and denominator. Main Q1 maps to RQ1; Main Q2 contains RQ2 and RQ3 as independently inspectable analyses; Main Q3 maps to RQ7 Primary. RQ4–RQ5 are secondary, RQ6 exploratory, and RQ7 Secondary is secondary/exploratory mitigation.

| RQ | Corrected estimator and result |
| --- | --- |
| RQ1 — Human Alignment | Agreement with human preference reference labels: **457/772 = 59.20%**, 95% CI 55.70–62.69%; Cohen's kappa **0.3230**, 95% CI 0.2698–0.3758. Per judge: Claude 85/187 = 45.45%, DeepSeek 127/188 = 67.55%, GPT 114/200 = 57.00%, Llama 131/197 = 66.50%. |
| RQ2 — Stochastic Consistency | Fixed-temperature strict complete-repetition consistency: **7,119/7,375 = 96.53%**, 1,475 strict-valid cells; 1,599/1,600 physical complete cells. Conditional returned-judgment sensitivity: **96.31%**, N=1,585. This evaluates repeatability/stability, not a temperature effect. |
| RQ3 — Position Sensitivity | 799/800 physical pairs; 759 valid; 549 decisive. Paired decisive flips: **96/549 = 17.49%**; all-paired disagreement: **193/759 = 25.43%**. Per-judge decisive flips: Claude 58/108 = 53.70%, DeepSeek 19/173 = 10.98%, GPT 3/111 = 2.70%, Llama 16/157 = 10.19%. The analysis follows canonical answer-identity remapping. |
| RQ4 — Controlled Redundant-Length Effect | 799/800 physical pairs; 682 eligible frozen-estimator pairs; **0/682 = 0.00%** stable controlled redundant-text variant wins. The numerator is exactly `variant_outcome == "VARIANT"` after valid/stable controlled-pair requirements. This does not estimate generic decision change or broad verbosity bias. |
| RQ5 — Controlled Presentation-Format Effect | 800/800 physical pairs; 716 eligible pairs; **0/716 = 0.00%** stable controlled presentation/list-prefix variant wins under the same valid/stable frozen estimator. It does not generalize to all formatting effects. |
| RQ6 — Counterbalanced Matched Source-Family Preference | **81/159 = 50.94%**, 95% CI 42.77–58.49%, coverage 159/480 = 33.13%. Claude: 25/29 = 86.21%; GPT: 50/66 = 75.76%; Llama: 6/64 = 9.38%. This is a counterbalanced matched source-family association with substantial heterogeneity, not causal self-bias evidence. |
| RQ7 PRIMARY — DUAL_SWAP | 799/800 physical linked triplets and N=597 matched retained decisions. Baseline **405/597 = 67.84%**; DUAL_SWAP **409/597 = 68.51%**; delta **+0.67 pp** (95% CI **−0.17 to +1.68 pp**). Coverage: baseline 774/799 = 96.87%, DUAL_SWAP 606/799 = 75.84%, delta −21.03 pp. The point estimate is slightly positive but its CI spans zero; the interpretation is small uncertain agreement change plus substantial coverage loss. |
| RQ7 SECONDARY — Multi-Judge | Planned N=1,611; four-valid=1,482; consensus-covered=1,125 (69.83%). Agreement: **808/1,125 = 71.82%** versus **66.80%** equal-weight individual comparator; delta **+5.02 pp** (95% CI **+4.16 to +5.89 pp**). This is positive only against its own frozen comparator on retained consensus-covered pairs. |

DUAL_SWAP is a within-judge presentation-consistency filter; Multi-Judge is a
cross-judge aggregation strategy. Their frozen units, comparators, and
estimands differ, so direct DUAL_SWAP-versus-Multi-Judge superiority is
**NOT_DEFENSIBLE**. Human labels are preference references, not ground truth;
none of these results proves universal bias, causal self-bias, or universally
improved reliability.

## Reproducibility release chain

- `evidence/final/phase11/` remains immutable historical evidence; digest
  `f1a1d6ffcb6f6fd5a5dd48f7b51a731d6b765a68ff76501bf6c0ef356e53ce13`.
- `evidence/final/rq6_counterbalanced/` remains the separate RQ6 addendum.
- `evidence/final/multijudge_consensus_v1/` remains immutable historical
  Multi-Judge evidence.
- `evidence/final/controlled_source_text_corrected_v1/` is the additive
  source-text-corrected evidence package and verifier.
- `evidence/final/research_release_v4/` is the current additive PostgreSQL
  release snapshot. It preserves v2/v3 and Phase 11 without rewriting them.

The React scientific pages consume `/api/controlled/results`; the route is
AnalysisRun-backed, accepts controlled evidence only, and does not substitute
historical, exploratory, or live-sandbox metrics. The Leaderboard, Diagnostics,
and Qualitative Explorer remain historical/exploratory views, while Live
Evaluation is a server-gated manual/exploratory sandbox. Its retained
operational records are excluded from historical telemetry and frozen RQ1–RQ7
evidence; exact provider-response replay is not guaranteed.

The dashboard's execution-accounting strip is database-wide: it includes
persisted historical and superseded controlled lineages for operational
transparency. It is not an RQ denominator; every final RQ estimate uses the
pinned authoritative AnalysisRuns above.

## Verified inference protocol and provider provenance

The human preference reference labels come from LMSYS MT-Bench Human Judgments. Canonical records link question ID and turn to exact source-model answer texts and SHA-256 answer hashes. Upstream `model_a`, `model_b`, and `tie` winners map to canonical `ANSWER_A`, `ANSWER_B`, and `TIE`; reversed source order reverses A/B but leaves TIE unchanged. Judge verdicts on swapped displays are mapped through the persisted presented answer IDs to canonical answer identity before comparison. Missing, ambiguous, or hash-mismatched identities are rejected. Two forensic turn-2 disambiguations retain their committed reconciliation lineage rather than inferring a label from a different raw row. Ties remain valid only where the particular estimator admits them, and each RQ applies its documented eligibility/exclusion rule.

The exact configured **judge** identifiers are `gpt-4o-mini`, `anthropic/claude-3-haiku`, `deepseek/deepseek-chat`, and `meta-llama/llama-3.3-70b-instruct`; these are distinct from historical candidate-answer source models (`alpaca-13b`, `claude-v1`, `gpt-3.5-turbo`, `gpt-4`, `llama-13b`, and `vicuna-13b`). The frozen `controlled-judge-pairwise-v1` prompt instructs impartial comparison of the question and two answers and requests JSON only. Its four required fields are `verdict`, `criteria_scores`, `confidence`, and `explanation`. Verdict accepts `ANSWER_A`, `ANSWER_B`, `TIE`, or `UNKNOWN`; only the first three are scientifically valid labels. The five criterion scores are strict integers 1–5, confidence a finite self-reported value in [0,1], and explanation nonempty text. The adapter may strip a code fence/isolate an apparent object, then validates the strict schema; malformed or extra fields become `INVALID_RESPONSE`, never heuristic labels.

The source-corrected execution manifest records historical and corrected-pass temperatures `0.0000` or `0.7000`, top-p `1.0000`, and provider request seeds `null`, `42`, or `20260818` (non-null seeds only for GPT). RQ2 has five planned repetitions in each exact fixed-configuration group; retries are operational attempts, not extra repetitions or a temperature-effects comparison. The separate four-judge Multi-Judge manifest specifies temperature `0`, top-p `1`, maximum output tokens `350`, and no provider request seed. Frozen analysis/bootstrap seeds are `20260818` for RQ1–RQ7 Primary/RQ6 and `20260823` for Multi-Judge; the clustered sensitivity seed is `20260912`. The frozen route policy `controlled-routing-v1` disallows fallback and validates requested/effective/observed model and provider provenance.

The `controlled-retry-v2` policy permits at most two retries for rate limits, temporary HTTP 5xx, or connection failure (2- and 8-second backoffs), and one retry for timeout (5-second backoff). Invalid/schema-invalid responses, refusals, authentication/configuration failures, provenance mismatches, budget blocks, unsupported parameters, and ambiguous attempts are terminal. Attempts are persisted before sending; bounded recovery preserves scientific inputs and never silently duplicates a successful pass. Fourteen terminal Claude observations remained unavailable after recovery. Their judge-specific, question-clustered missingness is handled by the applicable complete-case rules, without an MCAR or MAR claim. See [the detailed methodology record](docs/STUDY_METHODOLOGY.md) for the exact source and policy references.

## Statistical dependence and uncertainty

The frozen official 95% percentile bootstrap uses each estimator's logical analysis unit—typically a judge×pair cell or complete paired record, never an independently resampled presentation pass. RQ6 uses its counterbalanced logical unit and Multi-Judge resamples complete pair-level consensus records. Observations from the same original MT-Bench question may nevertheless be correlated. A separate deterministic 10,000-replicate **question-clustered bootstrap sensitivity analysis** (seed `20260912`) resampled original question IDs, preserving all turns, judges, repetitions, swaps, variants, and matched observations belonging to each sampled question. All substantive conclusions remained unchanged. This sensitivity **does not replace official frozen CIs** or AnalysisRuns. Its RQ7 Primary coverage-delta CI of **−24.62 to −17.64 pp** is sensitivity evidence only; no official frozen CI was reported for that quantity. See [the validation record](evidence/validation/question_clustered_bootstrap_sensitivity_v1.md).

Requested model identifiers, returned effective model identifiers, response
IDs, and routing provenance are persisted. `model_version` stores a provider
revision only when the response supplies one (for example, an OpenAI system
fingerprint); it remains null when an immutable vendor revision is not exposed
rather than being inferred or backfilled.

## Clean fresh-start reproducibility boundary

The normal fresh-start workflow uses the committed raw LMSYS snapshot
`data/human_judgment.jsonl` and the source-text-keyed canonical manifest
`data/canonical/source_corrected_study_v1.json`. It applies migrations to an
empty PostgreSQL database, then runs `scripts/build_dataset.py`. That builder
validates question/turn/model/text hashes before inserting data and fails closed
on a missing record, ambiguous identity, or hash mismatch. It never consults a
historical working database, legacy answer IDs, or insertion order.

The source-corrected study covers 80 distinct MT-Bench questions (preserved
upstream question IDs 81–160). Because MT-Bench has two turns per question,
the fresh build contains 160 turn-level prompt records; this is not a count of
160 distinct MT-Bench questions.

The separately documented historical/remediation tools and all frozen packages
remain available for audit, but are not prerequisites for this clean workflow.

## Current implementation layout

`backend/main.py` is the API entrypoint. The maintained backend domains are
`core/` (ORM, database, evidence pins), `data/` (canonical source data),
`evaluation/` (prompt, route, provider, retry, and execution safety),
`analysis/` (controlled and source-corrected estimators), `experiments/`
(counterbalanced RQ6), `multijudge/` (RQ7 secondary protocol), `historical/`
(required source-correction lineage), and `release/` (release construction and
verification).

The public reproducibility commands are `scripts/build_dataset.py`,
`scripts/run_evaluation.py`, `scripts/run_analysis.py`, and
`scripts/verify_reproducibility.py`.

The analysis command (`scripts/run_analysis.py`) exposes two provider-free modes:
1. **Frozen artifact verification** (`python scripts/run_analysis.py`): validates the committed/frozen final result and all expected metrics.
2. **Independent database recomputation** (`python scripts/run_analysis.py --recompute-from-db`): independently reconstructs RQ1–RQ7 metrics directly from the restored PostgreSQL database using `backend/analysis/source_corrected_full_population.py` and compares against the frozen release artifact.

The frozen package verifiers establish file integrity and pinned-record
provenance; they are not by themselves a release-dump restore test because they
reconcile with the configured database. The supported end-to-end release-v4
command is `python -m backend.release.verify_v4_api`: it checks the dump digest,
restores it to a uniquely named disposable database, reconciles the controlled
API and pinned AnalysisRuns against that restored database, independently
recomputes the analysis there, and drops only the database it created. PostgreSQL
tools resolve through `POSTGRES_BIN`, then `PATH`, with version-agnostic Windows
discovery only as a fallback.

Historical one-off reconstruction helpers
live under `tools/historical/`. The root `backend/database.py` and
`backend/controlled_models.py` modules are intentionally retained only as
compatibility shims for immutable frozen-package verifiers.
