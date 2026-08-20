# Phase 10 — Final Offline Scientific Analysis Report

**Date**: 2026-08-20  
**Phase**: 10 (Final Offline Scientific Analysis)  
**Status**: COMPLETE & FULLY VALIDATED  
**Evidence Source**: PostgreSQL Stored Controlled Evidence Only (Zero Provider Inference)

---

## 1. Provider Safety
- **Provider inference calls made**: **0** (OpenAI: 0, OpenRouter: 0)
- **API spend incurred**: **$0.000000**
- **Offline execution environment**: 100% local deterministic evaluation from stored PostgreSQL evidence.

---

## 2. Scientific Data Identity
- **DatasetVersion UUID**: `2f8c7bba-08b1-4d8b-8b0e-b564e8a61886`
- **Dataset Source Checksum (SHA256)**: `b2fff1524b199fb2d302b7c4ebd752a9a47d32bab68a232ab06b7b1e07fa1510`
- **Canonical Prompt Template Hash**: `e1d041bd6a1ec4f27efe6a3377d98ec0321af02b59ee9abedf64bf349ac9b299`
- **Routing Policy Fingerprint**: `bf8d0d1ef228f60e07ceff2e1da43eeefe8ae5538d439b5d9a4c325294b7030b`
- **Controlled Retry Policy**: `controlled-retry-v2`
- **Analysis Engine Version**: `phase4-analysis-v1`
- **Bootstrap Configuration**: Seed `20260818`, 10,000 percentile resamples, 95% Confidence Level.

---

## 3. Final Evidence Accounting

### A. Experimental Units (13,400 Total Planned)
- **SUCCEEDED Units**: 12,602 (94.04%)
- **Valid Scientifically Complete PARTIAL Units**: 523 (3.90%)
- **Terminal FAILED Units**: 275 (2.05%)
- **Pending Provider-Eligible Units**: 0 (0.00%)
- **Total Accounted**: **13,400 / 13,400 (100.0%)**

### B. Scientific Pass Slots (16,600 Total Planned)
- **Valid Returned Passes in SUCCEEDED Runs**: 15,182
- **Valid Returned Passes in PARTIAL Runs**: 1,046
- **Terminal Failed Pass Slots**: 372
- **Total Accounted Pass Slots**: **16,600 / 16,600 (100.0%)**

---

## 4. AnalysisRun Provenance Records

All 7 canonical research questions have published, completed `AnalysisRun` records in PostgreSQL:

| RQ | AnalysisRun UUID | Manifest UUID | Experiment UUID | Status | Metrics Count | Recompute Verification |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| **RQ1** | `63cd1939-05f4-42cf-a933-4094ac652eea` | `550e0ec5-e531-45fa-a1ea-422cc9710001` | `4d65d88e-3e9f-4e0c-9460-b2a10f57c3ca` | COMPLETED | 14 | **MATCH (0 mismatches)** |
| **RQ2** | `25949bbe-b962-4808-9830-f106bb3d1d42` | `0581763f-1fff-4092-a2f2-c60170eb8dbf` | `3f6294f6-cf5e-4c27-8c21-f162b93c594d` | COMPLETED | 1 | **MATCH (0 mismatches)** |
| **RQ3** | `4a5a5c97-6b63-4d33-9129-3d7048e96a87` | `816ba9b6-1dd4-40ac-abed-15e3e4dd896a` | `3b8ef1ab-f149-4458-9580-02c41fdea781` | COMPLETED | 4 | **MATCH (0 mismatches)** |
| **RQ4** | `13510c83-354c-49b1-811f-5e96a6b985e7` | `f63360e4-04c8-4815-86b5-eefeed78cb5b` | `d02a90f5-8096-48aa-9297-ee51e93a10ca` | COMPLETED | 3 | **MATCH (0 mismatches)** |
| **RQ5** | `bbfbcf03-1791-4892-a39c-418831260f35` | `494cf45e-f974-4f92-bc8f-f490d82d0f91` | `f7ebd809-6ad4-4ba0-8f19-2f24200ddeed` | COMPLETED | 3 | **MATCH (0 mismatches)** |
| **RQ6** | `ca9a1668-58b9-4a9d-8b0d-991c2b7a38ec` | `5491bd7b-2f59-4922-a4c2-ecbe38c57e0a` | `a3484b84-870d-4f01-85ad-df7d160c7efd` | COMPLETED | 1 | **MATCH (0 mismatches)** |
| **RQ7** | `d3773e0c-80dc-4235-aa46-ffd89af9face` | `55e58905-2265-49b3-87b7-1d55daa073ea` | `eccc037f-d331-47d7-a186-983ae58f3369` | COMPLETED | 20 | **MATCH (0 mismatches)** |

---

## 5. RQ1 — Human Alignment

- **Scientific Question**: How well do LLM judges agree with Human Preference Reference Labels?
- **Overall Agreement**: **0.5844** (95% CI: `[0.5506, 0.6195]`, $N = 770 / 800$ valid units).
- **Cohen's Kappa**: **0.3121** (95% CI: `[0.2579, 0.3652]`, $N = 770 / 800$).

### Judge Breakdown:
| Judge Model | Eligible N | Analyzed N | Exact Agreement | 95% CI | Cohen's Kappa | 95% CI | Tie Rate | Failures |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `deepseek/deepseek-chat` | 200 | 187 | **0.6845** | `[0.6203, 0.7487]` | **0.4682** | `[0.3678, 0.5684]` | 0.2086 | 13 |
| `meta-llama/llama-3.3-70b-instruct` | 200 | 196 | **0.6633** | `[0.5969, 0.7296]` | **0.4431** | `[0.3470, 0.5398]` | 0.2194 | 4 |
| `gpt-4o-mini` | 200 | 199 | **0.5528** | `[0.4874, 0.6231]` | **0.2647** | `[0.1652, 0.3642]` | 0.2362 | 1 |
| `anthropic/claude-3-haiku` | 200 | 188 | **0.4362** | `[0.3670, 0.5053]` | **0.0763** | `[-0.0154, 0.1678]` | 0.2074 | 12 |

---

## 6. RQ2 — Stochastic Consistency

- **Scientific Question**: Does the same judge produce stable decisions across repeated evaluations under controlled configurations?
- **Overall Within-Unit Consistency**: **0.9656** (95% CI: `[0.9604, 0.9707]`, $N = 1,474 / 1,712$ complete repetition groups).
- **Per-Judge Consistency**:
  - `deepseek/deepseek-chat`: **0.9712** (95% CI: `[0.9625, 0.9799]`, $N = 368 / 428$)
  - `gpt-4o-mini`: **0.9705** (95% CI: `[0.9618, 0.9792]`, $N = 373 / 428$)
  - `meta-llama/llama-3.3-70b-instruct`: **0.9664** (95% CI: `[0.9571, 0.9758]`, $N = 365 / 428$)
  - `anthropic/claude-3-haiku`: **0.9542** (95% CI: `[0.9431, 0.9652]`, $N = 368 / 428$)
- **Temperature / Configuration Contrast**: The final frozen RQ2 manifest establishes a single controlled baseline configuration; no secondary temperature arm is present in the dataset.

---

## 7. RQ3 — Position Sensitivity / Bias

- **Scientific Question**: Does swapping presented answer positions (AB vs BA) change the mapped original-answer decision?
- **Overall Paired Decisive Flip Rate**: **0.1670** (95% CI: `[0.1376, 0.1982]`, $N = 545 / 800$ decisive pairs).
- **All-Paired Disagreement Rate**: **0.2487** (95% CI: `[0.2183, 0.2804]`, $N = 756 / 800$ valid complete pairs).
- **Overall Slot Win Imbalance**: **0.1193** ($N = 545$).

### Judge Breakdown:
| Judge Model | Eligible Pairs | Decisive Analyzed | Paired Decisive Flip Rate | 95% CI | All Disagreement Rate | 95% CI | Slot Imbalance |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `anthropic/claude-3-haiku` | 200 | 129 | **0.2713** | `[0.1938, 0.3488]` | **0.3704** | `[0.3016, 0.4392]` | 0.0853 |
| `gpt-4o-mini` | 200 | 142 | **0.1901** | `[0.1268, 0.2535]` | **0.2667** | `[0.2051, 0.3282]` | 0.0282 |
| `meta-llama/llama-3.3-70b-instruct` | 200 | 134 | **0.1418** | `[0.0821, 0.2015]` | **0.1927** | `[0.1354, 0.2500]` | 0.1791 |
| `deepseek/deepseek-chat` | 200 | 140 | **0.0643** | `[0.0214, 0.1071]` | **0.1649** | `[0.1134, 0.2165]` | 0.1857 |

---

## 8. RQ4 — Controlled Redundant-Length Effect

- **Scientific Question**: Does redundant extra length influence a judge when factual content is preserved?
- **Controlled Variant Win Rate**: **0.0044** (95% CI: `[0.0000, 0.0102]`, $N = 685 / 800$).
- **Original Text Win Rate**: **0.0044** (95% CI: `[0.0000, 0.0102]`, $N = 685 / 800$).
- **Deterministic Variant Exclusions**: 115 units excluded due to strict length-perturbation validation contracts.

---

## 9. RQ5 — Controlled Presentation-Format Effect

- **Scientific Question**: Does formatting perturbation influence judgment when semantic content is preserved?
- **Controlled Format Variant Win Rate**: **0.0111** (95% CI: `[0.0042, 0.0195]`, $N = 719 / 800$).
- **Original Format Win Rate**: **0.0028** (95% CI: `[0.0000, 0.0070]`, $N = 719 / 800$).
- **Superseded RQ5 Evidence Isolation**: Exactly 226 pre-fix superseded runs contributed 0 passes to this analysis.

---

## 10. RQ6 — Matched Source-Family Preference

- **Scientific Question**: Does a judge prefer answers from its own source family under matched comparison?
- **Metric Status**: `UNBALANCED_PRESENTATION` / `NOT_ESTIMABLE` ($N = 0 / 600$).
- **Reason**: The frozen dataset pairs exhibit presentation-slot imbalance ($|Slot A - Slot B| > 1$) across matched source families, preventing causal self-preference estimation without confounding. Reported transparently as unestimable.

---

## 11. RQ7 — Baseline Single-Pass vs. Dual-Swap Mitigation

- **Scientific Question**: Can dual-pass mitigation reduce position sensitivity while maintaining human-preference agreement?
- **Single-Pass Baseline Human Agreement**: **0.6065** (95% CI: `[0.5712, 0.6405]`, $N = 765 / 765$).
- **DUAL_SWAP Mitigation Human Agreement**: **0.6878** (95% CI: `[0.6484, 0.7238]`, $N = 583 / 583$).
- **Alignment Delta**: **+0.0813** (+8.13 percentage points improvement).
- **Dual-Pass Stability**: **0.7661** (95% CI: `[0.7359, 0.7963]`, $N = 761$).
- **Coverage Trade-off**:
  - Baseline Valid Coverage: **0.9563** (95% CI: `[0.9413, 0.9700]`).
  - DUAL_SWAP Valid Coverage: **0.7288** (95% CI: `[0.6975, 0.7588]`).
  - Coverage Delta: **-0.2275** (trade-off of -22.75 percentage points coverage for +8.13 pp higher reference agreement).

---

## 12. Cross-Judge Multi-Metric Synthesis

| Judge Model | RQ1 Human Agreement | RQ1 Cohen's Kappa | RQ2 Stochastic Consistency | RQ3 Paired Decisive Flip Rate | RQ3 Slot Imbalance | RQ7 Mitigation Agreement Delta | RQ7 Mitigation Coverage Delta |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `deepseek/deepseek-chat` | **0.6845** | **0.4682** | **0.9712** | **0.0643** | 0.1857 | **+0.0768** | -0.1950 |
| `meta-llama/llama-3.3-70b-instruct` | **0.6633** | **0.4431** | **0.9664** | **0.1418** | 0.1791 | **+0.0842** | -0.2100 |
| `gpt-4o-mini` | **0.5528** | **0.2647** | **0.9705** | **0.1901** | **0.0282** | **+0.0721** | -0.2350 |
| `anthropic/claude-3-haiku` | **0.4362** | **0.0763** | **0.9542** | **0.2713** | 0.0853 | **+0.0924** | -0.2700 |

---

## 13. Failure & Data Quality Accounting

| RQ | Planned Units | Succeeded Units | Valid Partial Units | Failed Units | Planned Passes | Valid Passes | Failed Pass Slots | Failure Rate | Primary Failure Cause |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **RQ1** | 800 | 782 | 0 | 18 | 800 | 782 | 18 | 2.25% | Rate limit / upstream transient |
| **RQ2** | 8,000 | 7,862 | 0 | 138 | 8,000 | 7,862 | 138 | 1.73% | Rate limit / upstream transient |
| **RQ3** | 800 | 573 | 204 | 23 | 1,600 | 1,554 | 46 | 2.88% | Dual-pass retry exhaustion |
| **RQ4** | 800 | 699 | 64 | 37 | 1,600 | 1,526 | 74 | 4.63% | Dual-pass retry exhaustion |
| **RQ5** | 800 | 724 | 56 | 20 | 1,600 | 1,560 | 40 | 2.50% | Dual-pass retry exhaustion |
| **RQ6** | 600 | 596 | 0 | 4 | 600 | 596 | 4 | 0.67% | Rate limit / upstream transient |
| **RQ7** | 1,600 | 1,366 | 199 | 35 | 2,400 | 2,348 | 52 | 2.19% | Baseline & Dual retry exhaustion |
| **TOTAL** | **13,400** | **12,602** | **523** | **275** | **16,600** | **16,228** | **372** | **2.05%** | **Controlled Retry-v2 Policy Exhaustion** |

---

## 14. Generated Artifacts & Machine-Readable Tables

### Tables (`exports/phase10/tables/`):
1. `table_rq1_human_alignment.csv` / `.json`
2. `table_rq2_consistency.csv` / `.json`
3. `table_rq3_position_sensitivity.csv` / `.json`
4. `table_rq4_redundant_length.csv` / `.json`
5. `table_rq5_format_effect.csv` / `.json`
6. `table_rq6_source_family.csv` / `.json`
7. `table_rq7_mitigation.csv` / `.json`
8. `table_cross_judge_summary.csv` / `.json`
9. `table_failure_accounting.csv` / `.json`
10. `table_analysis_provenance.csv` / `.json`

### Consolidated Data:
- `exports/phase10/phase10_metrics_summary.json`
- `exports/phase10/phase10_analysis_provenance.json`

### Publication Charts (`exports/phase10/charts/`):
1. `rq1_agreement_by_judge.png`
2. `rq1_kappa_by_judge.png`
3. `rq2_consistency_by_judge.png`
4. `rq3_paired_flip_rate_by_judge.png`
5. `rq3_slot_win_imbalance.png`
6. `rq4_variant_preference_by_judge.png`
7. `rq5_format_preference_by_judge.png`
8. `rq7_baseline_vs_dual_swap_alignment.png`
9. `rq7_coverage_tradeoff.png`
10. `cross_judge_synthesis.png`

---

## 15. Claim-Safety & Methodological Boundaries

- **Human Reference Labels**: Used strictly as reference consensus, not unassailable "ground truth".
- **Position Sensitivity**: Distinguished paired swap sensitivity from general stochastic instability.
- **Controlled Perturbations**: Avoided sweeping claims of "verbosity bias" (RQ4) or "format preference" (RQ5); scoped strictly to exact controlled text/format manipulations.
- **Mitigation Trade-Offs**: Reported DUAL_SWAP as an explicit trade-off between higher reference alignment (+8.13 pp) and reduced operational coverage (-22.75 pp), rather than claiming bias was "eliminated".
- **No Composite Fabrications**: Avoided declaring an arbitrary "best judge" without a pre-specified utility function.

---

## 16. Phase 11 Readiness

- **Offline Validation**: 100% complete.
- **Provider Calls**: 0 calls, $0 spend.
- **Test Suite**: 5/5 Phase 10 tests passed; 135/135 total provider-free test suite passing.
- **Status**: **READY FOR PHASE 11 IMMUTABLE EVIDENCE FREEZE**.
