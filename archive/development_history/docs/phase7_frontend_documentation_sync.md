# Phase 7: frontend and documentation synchronization

## Evidence routing

| UI area | Route/data source | Evidence class | Status |
| --- | --- | --- | --- |
| Leaderboard | `/api/leaderboard` | `LEGACY_EXPLORATORY` | Historical judge-relative ranking |
| Diagnostics | `/api/stats/bias`, `/api/consistency`, `/api/stats/self-preference` | `LEGACY_EXPLORATORY` | Observational telemetry |
| Synthesis | `/api/stats/macro-benchmark` | `LEGACY_EXPLORATORY` | Historical comparison only |
| Qualitative explorer | `/api/qualitative/*` | `LEGACY_EXPLORATORY` | Historical examples |
| Live Evaluation | `/api/evaluate*` | `LIVE_SANDBOX` | Interactive/manual only |
| Controlled Experiments | `/api/controlled/results` | `CONTROLLED` | `NO_CONTROLLED_EVIDENCE` until real execution |

`PLANNED` is a presentation state for the frozen RQ1–RQ7 protocols.
`DRY_RUN_MOCK` is rejected by final controlled views and may be shown only in
an explicitly development/debug context with a Mock / Dry Run badge.

## Current controlled status

All RQ1–RQ7 protocols are READY and their offline validation PASSED. Controlled
provider execution has NOT YET RUN; controlled evidence is NONE YET. The
frontend therefore renders **NO CONTROLLED EVIDENCE YET**, never a fallback
legacy number or a placeholder zero metric.

Future controlled metric rendering consumes the Phase 4 serialized contract:
metric/value, numerator/denominator, eligible/analyzed N, ties, unknowns,
failures, exclusions, CI, status, judge, condition, analysis version, and
evidence class. It does not recompute scientific formulas in TypeScript.

## Terminology

- Human Preference Reference Labels, not ground truth or human accuracy.
- Judge-relative Pairwise Ranking, not true model merit.
- Paired Decisive Flip Rate (controlled) and Slot-Win Imbalance (legacy) are
  distinct.
- Exploratory Length Association is distinct from Controlled
  Redundant-Length Effect.
- Controlled Format Effect and Matched Source-Family Preference remain planned;
  no bias is described as confirmed.
- RQ7 will display signed mitigation deltas, including negative trade-offs and
  NOT_ESTIMABLE results, rather than a pre-decided improvement claim.
