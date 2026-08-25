# LLM-as-a-Judge Reliability Lab: Current Technical and Scientific Record

## Authority and evidence boundary

The current controlled science is the source-corrected full-population analysis
`source-corrected-complete-case-full-population-analysis-v2`, frozen in
[`evidence/remediation/source_corrected_complete_case_full_population_analysis_v2.json`](evidence/remediation/source_corrected_complete_case_full_population_analysis_v2.json)
(SHA-256 `ace75cfb15412c2070b848f048ad419ae70d46162c7b66d52ee4302432031d97).
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
offline re-parsing. The missing observations are judge-specific and
concentrated in a small subset of questions, turns, and categories. Analyses
therefore use explicitly reported complete-case populations, without claiming
MCAR or MAR.

## Corrected research results

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
Evaluation is a manual sandbox guarded by the server-side provider gate.
