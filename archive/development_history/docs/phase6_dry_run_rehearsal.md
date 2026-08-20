# Phase 6 controlled execution rehearsal

This runner is deliberately mock-only. `ExecutionProfile(mock_only=False)` is
rejected at construction and Phase 6 itself uses only
`DeterministicMockProvider`. `ControlledRunner.execute_real()` is now a thin,
fail-closed delegation to the separate `ControlledRealRunner`; without a
complete authorized REAL/PILOT profile it raises `PermissionError` before any
transport.

## Frozen workload

Snapshot `live-db-0004-frozen`, protocol `phase3-controlled-v1`, final frozen
prompt template `controlled-judge-pairwise-v1` (SHA-256
`e1d041bd6a1ec4f27efe6a3377d98ec0321af02b59ee9abedf64bf349ac9b299`),
base cap 200 per eligible judge/RQ. `judge-pairwise-structured-v1` was an
earlier Phase 6 rehearsal label and is not the final pre-pilot prompt.

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

The mock-only Phase 6 preflight derives token estimates from stored answers and
deliberately reports `PRICING VERIFICATION REQUIRED`: it is not a billing
estimate. This is not a statement about the real execution contract. The
separate real runner uses the frozen, project-owner-approved
`pricing-config-v1` configuration and reserves call/token/USD capacity before
each provider attempt.
