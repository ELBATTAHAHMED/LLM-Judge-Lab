# Phase 5 offline integration validation

## Coverage map

| Layer | Existing phase coverage | Phase 5 integration coverage |
| --- | --- | --- |
| Alembic, ORM, provenance | Phase 1 | Full isolated Dataset → Experiment → Manifest → Unit → Run → Pass round trip |
| Registry and structured response validation | Phase 2 | Mock outcomes carried through persistence and analysis adapters |
| Protocols, variants, manifests | Phase 3 | Variant provenance round trip, deterministic manifest/unit IDs, 16,600-call arithmetic |
| Authoritative metrics | Phase 4 | Persisted run/pass outputs converted to controlled-only RQ metric inputs |

`test_phase5_offline_integration.py` runs only against temporary SQLite
databases and deterministic mocks. It has no provider SDK/client construction.

## Deliberate static frontend/backend finding

The current live API/frontend schemas do not yet consume `MetricResult` from
the authoritative Phase 4 layer. The static test records that mismatch rather
than silently presenting legacy telemetry as controlled evidence. Frontend/API
synchronization remains later work.

## Resume policy proof

Reusing a run idempotency key now returns an existing non-pending controlled
run before evaluation. Completed runs are skipped; provider/timeouts are
classified retryable; invalid responses are non-retryable; pending and partial
runs remain pending for a future explicit resume policy. This makes retry count
and scientific repetition index independently auditable.
