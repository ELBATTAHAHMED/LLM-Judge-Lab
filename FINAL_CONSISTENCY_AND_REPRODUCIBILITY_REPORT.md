# Final Consistency and Reproducibility Report

Date: 2026-08-20  
Scope: provider-free consistency cleanup only. No experiment, database evidence,
AnalysisRun, DatasetVersion, or frozen Phase 11 file was modified.

1. **Conflicting final results:** active final pages and documentation were
   checked against frozen Phase 11 evidence. No superseded RQ3 value remains
   in active project-facing material.
2. **Canonical RQ3:** final documentation records 16.70% decisive flips and
   24.87% all-paired disagreement; per-judge decisive flips are Claude 27.13%,
   GPT-4o-mini 19.01%, Llama 14.18%, and DeepSeek 6.43%.
3. **RQ6 safety:** final RQ6 is consistently titled *Matched Source-Family
   Preference* and rendered as **NOT ESTIMABLE — UNBALANCED_PRESENTATION**.
   The retained diagnostic is explicitly legacy exploratory telemetry.
4. **RQ7 wording:** README, report, and synthesis describe increased agreement
   among retained decisions together with the valid-coverage reduction; no
   unqualified reliability-improvement claim remains.
5. **RQ4/RQ5 scope:** final text now confines conclusions to controlled
   redundant added text and the implemented presentation-format transformation.
6. **Live Sandbox:** the browser route, navigation item, client execution
   methods, and unused page were removed. Backend capability remains separately
   authorized and disabled by default; it is not connected to final evidence.
7. **Legacy cleanup:** `/api/stats/macro-benchmark` and
   `/api/leaderboard/calculate` are no longer registered. The historical
   leaderboard, diagnostics, and qualitative views remain labeled
   `LEGACY_EXPLORATORY`.
8. **README reproducibility:** added the verified clone, environment,
   PostgreSQL restore, backend/frontend startup, controlled-results, and offline
   verifier workflow. It explicitly states that normal startup and final
   dashboard reproduction require no provider calls.
9. **Dataset provenance:** README and the consolidated report now identify the
   DatasetVersion `2f8c7bba-08b1-4d8b-8b0e-b564e8a61886`, SHA-256,
   source/raw JSONL files, `unordered-pair-consensus-v1` policy, 1,615
   canonical pairs, controlled-variant lineage, and final entity counts.
10. **Licenses:** repository source files did not provide verifiable source
    license/attribution metadata; both documents state that external
    verification is required.
11. **Health:** `/health` now returns structured `healthy` or `unhealthy`
    dependency status and never includes database exception text or credentials.
12. **No-data semantics:** empty legacy bias and consistency telemetry now use
    `LEGACY_EXPLORATORY`, `status: NO_DATA`, `n: 0`, and nullable unavailable
    metrics. Measured zeroes remain numeric where observations exist.
13. **Final frontend source:** `/controlled-results` and `/synthesis` use only
    `useControlledResults` → `/api/controlled/results`; they do not consume
    legacy CSV, macro-benchmark, or static final values.
14. **Validation:** targeted backend safety/API tests passed (20); the full test
    suite collects 143 tests without the obsolete archived-runner test. Frontend
    tests passed (12), TypeScript typecheck and production build passed. The
    expensive database/final-analysis recomputation tests were intentionally not
    executed because this scope forbids recomputing final metrics.
15. **Frozen evidence:** `VERIFY_PACKAGE.py` passed after the cleanup. Phase 11
    root digest remains
    `f1a1d6ffcb6f6fd5a5dd48f7b51a731d6b765a68ff76501bf6c0ef356e53ce13`.
16. **Provider use:** 0 provider calls; $0 spend.
17. **Remaining non-academic blockers:** none identified for final dashboard
    reproduction. PostgreSQL must be available locally before restoring the
    supplied snapshot, as documented.
18. **Release:** commit and tag `final-consistency-reproducibility-v1` record
    this provider-free cleanup.

FINAL CONSISTENCY CLEANUP COMPLETE — CANONICAL RESULTS UNIFIED, LEGACY RISKS ISOLATED, REPRODUCIBILITY DOCUMENTED
