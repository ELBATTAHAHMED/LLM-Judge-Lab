# Phase 4 authoritative controlled metrics

`backend/phase4_metrics.py` is the sole final controlled-metric source at
`phase4-analysis-v1`. It accepts only records marked `CONTROLLED`; it rejects
legacy, live-sandbox, and planned records by default.

## Metric audit and isolation

| Existing path | Classification | Controlled final use |
| --- | --- | --- |
| `analyze_results.py` | Legacy/exploratory historical agreement and slot analysis | Not authoritative |
| `analyze_consistency.py` | Legacy/exploratory; historical prompt/group logic and A-slot source comparison | Not authoritative |
| `stochastic_test.py` | Legacy empirical runner; prompt-level grouping | Not authoritative |
| `generate_perturbations.py` | Legacy perturbation runner; semantic additions and fixed B slot | Not authoritative |
| `main.py` telemetry and macro endpoints | Frontend/live-sandbox reporting | Not authoritative |
| `phase3_metrics.py` | Protocol/planning validation only | Not final evidence |
| `phase4_metrics.py` | Controlled-only, versioned metric contract | Authoritative |

Legacy files are retained solely to reproduce or inspect historical outputs.
They are **LEGACY / EXPLORATORY — NOT FOR CONTROLLED FINAL EVIDENCE**.

## Shared result contract

Every result provides a metric/version, value, numerator/denominator,
eligible/analyzed/excluded counts, tie/unknown/invalid/failure/missing counts,
status, notes, and (where applicable) reproducible 95% bootstrap CI metadata.
No-data and invalid denominators return an explicit `NO_DATA`,
`NOT_ESTIMABLE`, `INSUFFICIENT_ELIGIBLE_UNITS`, or related status—not zero.

## Frozen formulas and bootstrap units

- RQ1 exact agreement: matching valid A/B/TIE human-reference and judge labels
  divided by valid comparable units; Cohen's kappa uses those three classes.
- RQ2 consistency: mean within-exact-configuration modal verdict proportion;
  bootstrap resamples full repeated-unit groups.
- RQ3 decisive flip: mapped-original winner disagreement divided by complete
  two-pass decisive pairs; slot-win imbalance is reported independently.
- RQ4/RQ5: validated controlled variant wins divided by valid controlled variant
  pairs; rejected variants remain counted.
- RQ6: balanced matched self-family wins divided by valid source-complete pairs.
- RQ7: matched `mitigation - baseline` absolute deltas, preserving negative,
  zero, and trade-off outcomes. No common matched metric is not estimable.

Bootstrap defaults are 10,000 iterations, 95% confidence, and a supplied
analysis seed. Tests use smaller iteration counts only for speed.
