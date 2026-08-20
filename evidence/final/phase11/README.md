# Final Evidence Package

This immutable Phase 11 package freezes the final controlled evidence and the validated Phase 10 analysis for the *LLM-as-a-Judge Reliability Lab*. It contains no API keys and verification requires no provider calls or database writes.

## Authority and separation

`evidence/` contains only final `CONTROLLED` science. `audit_history/pilot/` is technical real-wire validation only and is not included in final metrics. `audit_history/superseded_rq5/` preserves `PRE_FIX_RQ5_RAW_ANSWER_MATERIALIZATION` history and is excluded from authoritative analysis.

## Verify

Run `python VERIFY_PACKAGE.py` from this directory. The verifier validates file hashes, identities, accounting, isolation, and traceability. A successful run ends with `FINAL EVIDENCE PACKAGE VERIFIED`.

## Traceability

Each `TRACEABILITY_INDEX.json` metric references its AnalysisRun, manifest, experiment, deterministic controlled evidence indexes, dataset identity, and Phase 10 artifact. Confidence intervals are percentile bootstrap intervals over unit-level paired observations, seed `20260818`, 10,000 resamples, 95% confidence.

## Limitations

This package freezes observed controlled evidence; it does not prove causal generalization beyond the specified dataset, judges, frozen routes, protocol, and configured conditions. RQ6 is retained as `NOT ESTIMABLE` because of unbalanced presentation. RQ7 records a trade-off, not bias elimination.

Python 3.11+ is required for the exporter; the offline verifier uses only the standard library.
