# Phase 8: reuse versus rerun audit

This is a read-only audit. No record is promoted from legacy to controlled.

## Master reuse matrix

| Data / artifact | Count | Reuse class | Purpose | Final controlled evidence? | New API? | Reason |
| --- | ---: | --- | --- | --- | --- | --- |
| Prompts | 107 | `REUSE_AS_DATASET` | Frozen experiment input | Yes, as input | No | Stable prompt identities/categories |
| Answers | 2,139 (2 empty) | `REUSE_AS_DATASET` | Frozen experiment input | Yes, eligible subset | No | Phase 3 excludes empty-answer units by RQ |
| Human preferences | 2,396 (591 ties) | `REUSE_AS_REFERENCE` | Human Preference Reference Labels | Yes, as reference | No | 0 invalid winners; 0 duplicate ordered pairs |
| Historical judge decisions | 19,168 | `REUSE_AS_EXPLORATORY` | Historical alignment/ranking/diagnostics | No | Yes for final replacement | Missing frozen execution provenance |
| Historical calibrated decisions | 9,584 | `REUSE_AS_EXPLORATORY` | Calibration history/debugging | No | Yes | Final row only; no structured independent pass records |
| Live sandbox decisions | 43 | `REUSE_AS_EXPLORATORY` | Demo/debugging | No | Yes | `LIVE_SANDBOX` |
| RQ2 raw stochastic CSV | 500 | `REUSE_AS_EXPLORATORY` | Historical consistency context | No | Yes | Prompt-only grouping, no answer IDs; only T=0.0 |
| RQ2 summary CSV | 59 | `REUSE_FOR_VALIDATION` | Regression/display validation | No | Yes | Aggregate metric only |
| Perturbation CSV | 200 | `REUSE_AS_EXPLORATORY` | Legacy variant comparison | No | Yes | Semantic/confounded transformations, no counterbalancing |
| RQ6 raw decisions | Included above | `REUSE_AS_EXPLORATORY` | Source-family descriptive analysis | No | Yes | No frozen config/provenance or balanced allocation proof |
| Phase 6 rehearsal | 16,600 mock passes | `REUSE_FOR_VALIDATION` | End-to-end regression validation | No | Yes | `DRY_RUN_MOCK` |
| Frozen manifests | 7 / 13,400 units | `REUSE_AS_DATASET` | Future execution plan | Yes, as plan | No | Deterministic frozen protocol |

## Provenance decision rule

A historical provider result can be considered a `FINAL_CONTROLLED_CANDIDATE`
only if every frozen dimension is recoverable and compatible: dataset snapshot,
exact prompt/answers, judge/provider/effective model, protocol/template,
temperature/top-p/seed policy, repetition, presentation order, variant, and
condition. Partial provenance is insufficient; an aggregate cannot replace raw
passes. No historical `JudgeDecision` row contains the needed fields, so there
are **0 candidates** and **0 approved final reuses**.

## RQ decisions

| RQ | Existing material | Reusable purpose | Final controlled decision | Missing requirement | New calls |
| --- | --- | --- | --- | --- | ---: |
| RQ1 | Four historical judge families | Exploratory agreement/kappa | No | provider/effective model, template, config, snapshot, protocol | 800 |
| RQ2 | 500 raw trials; 59 summaries | Exploratory consistency | No | exact answer pair/config groups, T=0.7, complete provenance | 8,000 |
| RQ3 | 9,584 calibrated final rows | Calibration history | No | independently persisted AB and BA passes | 1,600 |
| RQ4 | 100 verbosity-padding records | Exploratory contrast | No | validated redundant-only variants, both orders | 1,600 |
| RQ5 | 100 markdown-injection records | Exploratory contrast | No | normalized content equivalence, both orders | 1,600 |
| RQ6 | Historical source-labelled answer pairs | Exploratory association | No | balanced/source-family controlled allocation and config provenance | 600 |
| RQ7 | Baseline/calibrated historical rows | Historical comparison/debugging | No | matched baseline/dual raw passes and authoritative metrics | 2,400 |

The RQ2 CSV contains only temperature `0.0`, is grouped by `prompt_id`, and
has no answer pair IDs. The historical calibrated runner embedded two
verdicts in a free-text reasoning field but persisted only one final
`JudgeDecision`; it therefore has `MISSING_PASS_LEVEL_DATA` for RQ3/RQ7.
The old verbosity padding adds contextual language; markdown injection adds
semantic headings/labels such as “Core Summary” and “Primary Point.” Both fail
the frozen causal-control standard.

## Exact-match and call-saving conclusion

```text
Frozen planned calls:             16,600
Exact historical candidate calls:      0
Approved final reusable calls:         0
Unavoidable new calls:            16,600
```

The historical API spend remains valuable for exploratory comparison,
debugging, regression tests, methodology development, and explaining why the
stronger protocol was needed. It does not replace a final controlled call.

Future necessary calls remain unchanged: GPT-4o-mini 4,200; Claude Haiku
4,200; DeepSeek Chat 4,000; Llama 3.3 70B 4,200. The minimum valid strategy is
to reuse the dataset, human references, source metadata, deterministic
variants, manifests, and historical context; execute only the 16,600 frozen
provider judgments after a separately authorized pilot.
