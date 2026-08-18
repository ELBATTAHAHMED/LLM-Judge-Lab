# Phase 6 controlled execution rehearsal

This runner is deliberately mock-only. `ControlledRunner.execute_real()` always
raises `PermissionError`; `ExecutionProfile(mock_only=False)` is rejected at
construction. The only Phase 6 provider is `DeterministicMockProvider`.

## Frozen workload

Snapshot `live-db-0004-frozen`, protocol `phase3-controlled-v1`, prompt
template `judge-pairwise-structured-v1`, base cap 200 per eligible judge/RQ:

| RQ | Controlled units/runs | Passes / provider-equivalent calls |
| --- | ---: | ---: |
| RQ1 | 800 | 800 |
| RQ2 | 8,000 | 8,000 |
| RQ3 | 800 | 1,600 |
| RQ4 | 800 | 1,600 |
| RQ5 | 800 | 1,600 |
| RQ6 | 600 | 600 |
| RQ7 | 1,600 | 2,400 |
| **Total** | **13,400** | **16,600** |

RQ7 has 800 baseline and 800 dual-swap condition-specific runs. Its baseline
uses one pass and its dual-swap condition uses two; this explains why a prior
13,400-run reconciliation must not be reported as 12,600.

## Safety and persistence

The full test reads the local frozen source database, then persists only to a
pytest-created temporary SQLite database through `ControlledPersistence`:
`DatasetVersion -> Experiment -> Manifest -> Condition -> Unit -> Run -> Pass`.
It does not write to the live research database. The dry-run records and exports
are labelled `DRY_RUN_MOCK` / `MOCK / DRY-RUN — NOT SCIENTIFIC EVIDENCE`.

`resume_state` classifies successful observations as completed, `TIMEOUT` and
`PROVIDER_ERROR` as retryable, invalid responses as non-retryable, and pending
or partial work as pending. Stable unit IDs/idempotency keys cause a repeated
dry-run of the same isolated snapshot to reuse manifests, units, runs, and
passes; it creates zero duplicate runs/passes.

## Controlled-result API contract

The mock analysis serialization contains `rq`, `judge`, `condition`, `metric`,
`value`, `numerator`, `denominator`, `eligible_n`, `analyzed_n`, `ties`,
`unknowns`, `failures`, `excluded`, `ci_low`, `ci_high`, `status`,
`analysis_version`, and `evidence_class`. The frontend contract guard accepts
null numeric values and `NOT_ESTIMABLE`; it never treats missing values as zero.
The legacy dashboard endpoints are intentionally not connected to dry-run
evidence. Their older charts and scientific wording remain a frontend
synchronization task.

## Cost preflight

Preflight derives input estimates from the stored answers plus the frozen
template overhead and reserves 350 output tokens per planned call. It reports
`PRICING VERIFICATION REQUIRED` rather than using an unfrozen price table.
`enforce_budget` can reject calls/tokens before execution; USD enforcement
remains blocked until verified pricing is explicitly frozen.
