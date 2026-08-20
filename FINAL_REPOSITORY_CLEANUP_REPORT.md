# Final Repository Cleanup Report

## Scope and safeguards

This release reorganizes repository code and historical material only. No LLM
provider was called, no experiment was run, and no database or final metric was
modified. The frozen Phase 11 evidence package remains at
`evidence/final/phase11/`; its verified package-root digest is
`f1a1d6ffcb6f6fd5a5dd48f7b51a731d6b765a68ff76501bf6c0ef356e53ce13`.

## Active code naming

The active controlled-experiment modules now use descriptive names:

| Previous name | Active name |
| --- | --- |
| `phase3_planning.py` | `experiment_planning.py` |
| `phase3_protocols.py` | `experiment_protocols.py` |
| `phase3_transforms.py` | `controlled_transforms.py` |
| `phase3_metrics.py` | `reliability_metrics.py` |
| `phase4_metrics.py` | `controlled_analysis_metrics.py` |

Their tests were renamed consistently and all active imports were updated. Stable
database identifiers, migration names, protocol versions, and evidence metadata
retain their original names because they are provenance-bearing identifiers.

## Archived material

Historical documentation is under `archive/development_history/docs/`.
One-time execution, ingestion, calibration, perturbation, and provider
connectivity scripts are under `archive/legacy_execution/`. Release-time evidence
construction tools are under `archive/release_tools/`. Their repository-root
paths were updated so they remain manually inspectable historical tools, but they
are no longer mounted in the active backend or standard test suite.

Superseded local backups, former planning artifacts, reports, and exploratory
outputs are retained in ignored archive locations. The final database snapshot
`backups/judgelab-phase11-final-evidence-20260820.dump`, Phase 10 exports, and
all Phase 11 evidence remain in their authoritative locations. Root qualitative
CSV compatibility copies were intentionally retained because the active API
still supports them as a fallback.

## Removed generated material

Validation-generated Python caches, pytest cache, and frontend build output were
removed. No source, active data, final evidence, or reproducibility artifact was
deleted.

## Validation

| Check | Result |
| --- | --- |
| Python compilation of active and archived scripts | PASS |
| Active methodology, analysis, integration, recovery, RQ6/RQ7, evidence, and runtime-safety tests | PASS (55 tests) |
| Active dry-run safety tests (excluding the large optional local-data rehearsal) | PASS (3 tests) |
| Frontend tests | PASS (12 tests) |
| Frontend production build | PASS |
| Phase 11 offline verifier | PASS |
| Frozen package root digest | Unchanged: `f1a1d6ffcb6f6fd5a5dd48f7b51a731d6b765a68ff76501bf6c0ef356e53ce13` |
| Provider calls | 0 |

The optional full local-data mock rehearsal was not executed during this cleanup:
it performs a large provider-free simulation against the local database and is
outside an organization-only release. The active dry-run contract, provider
gate, and final-evidence verification tests cover the changed import and archive
paths.

## Release result

The repository has a clear active surface, archived historical tooling, retained
reproducibility material, and no active references to the superseded execution
script paths.
