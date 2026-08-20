# LLM-as-a-Judge Reliability Lab: Final Technical and Scientific Report

## 1. Project Overview

**LLM-as-a-Judge Reliability Lab: Measuring and Mitigating Biases in Automatic
Evaluation of Generated Responses** is a reproducible full-stack research
system for studying pairwise LLM judgments. Its final contribution is a
controlled, provenance-preserving evaluation of alignment with human preference
reference labels, judgment consistency, presentation sensitivity, narrowly
defined counterfactual effects, and a dual-swap mitigation trade-off.

The final system keeps final controlled evidence separate from historical,
exploratory, pilot, and live-sandbox material. It supports transparent analysis
and inspection rather than treating an LLM judgment as objective truth.

## 2. Final Research Questions

| RQ | Canonical question |
| --- | --- |
| RQ1 | Human Alignment |
| RQ2 | Stochastic Consistency |
| RQ3 | Position Sensitivity |
| RQ4 | Controlled Redundant-Length Effect |
| RQ5 | Controlled Presentation-Format Effect |
| RQ6 | Counterbalanced Matched Source-Family Preference |
| RQ7 | Mitigation Trade-off |

## 3. Final Dataset and Experimental Design

The final DatasetVersion is `2f8c7bba-08b1-4d8b-8b0e-b564e8a61886`
(`controlled-final-plan-v1`), with dataset SHA-256
`b2fff1524b199fb2d302b7c4ebd752a9a47d32bab68a232ab06b7b1e07fa1510`.
Its source name is `judgelab-canonical-human-reference`; its legacy
whole-database import metadata records 107 prompts, 2,139 answers, and 1,615
human-reference pairs under `unordered-pair-consensus-v1`. These counts do not
describe the final controlled source subset: all canonical controlled units use
the 80 raw prompts with IDs 81–160. Checked-in source material
consists of `data/question.jsonl`, `data/human_judgment.jsonl`, and the model
answer JSONL files. The recorded lineage normalizes those judgments into the
canonical unordered reference pairs, applies the frozen import filters, then
creates checksum-linked controlled RQ4/RQ5 variants. Dataset version metadata,
exclusions, variants, and final controlled inclusion are preserved in the Phase
11 package. The additive release records the reconciliation and raw-file hashes
in `evidence/final/research_release_v2/dataset/`. License/attribution metadata
requires external verification.

The frozen Phase 11 controlled execution comprises **13,400 units** and
**16,600 pass slots**. The later, separate counterbalanced RQ6 lineage adds
480 units and 960 pass slots; it is pinned independently and does not alter
the frozen Phase 11 package. Its deterministic selection manifest and concise
executed-lineage references are retained in
`evidence/final/rq6_counterbalanced/`.
Its four configured judges are `gpt-4o-mini`,
`anthropic/claude-3-haiku`, `deepseek/deepseek-chat`, and
`meta-llama/llama-3.3-70b-instruct`. Routing is recorded per controlled run;
the final provenance includes the prompt fingerprint, route fingerprint, retry
policy, requested/effective-model data where returned, presentation order,
condition, repetition identity, and deterministic unit/manifest identity.

Final scientific metrics accept `CONTROLLED` evidence only. `PILOT`,
`SUPERSEDED_CONTROLLED`, `LIVE_SANDBOX`, and `LEGACY_EXPLORATORY` evidence are
kept for audit or historical interpretation but are not final RQ evidence.

## 4. Final Execution Accounting

All frozen Phase 11 controlled units are terminally accounted:

| Unit outcome | Count |
| --- | ---: |
| SUCCEEDED | 12,602 |
| Valid PARTIAL | 523 |
| FAILED | 275 |
| **Total** | **13,400** |

| Pass-slot outcome | Count |
| --- | ---: |
| Valid returned passes | 16,228 |
| Failed pass slots | 372 |
| **Total** | **16,600** |

There are **0 pending** units. A `PARTIAL` unit is terminally accounted but
has incomplete required pass-level output; valid returned observations are used
only where the relevant RQ's predeclared denominator and pairing rules allow
them. Missing or failed passes remain explicit and are not converted to ties,
zeros, or fabricated outcomes.

## 5. Final Scientific Results

| RQ | Authoritative final result |
| --- | --- |
| RQ1 | 58.44% agreement with human preference reference labels (95% CI 55.06–61.95%), Cohen's kappa 0.3121, N=770. |
| RQ2 | Primary strict complete-repetition consistency: 96.74% (95% CI 96.22–97.23%), N=1,428 all-valid groups. Conditional returned-judgment sensitivity: 96.56%, N=1,474. No final temperature comparison is estimable. |
| RQ3 | 16.70% paired decisive flip rate (95% CI 13.76–19.82%), N=545 decisive pairs; 24.87% all-paired disagreement, N=756 complete pairs. |
| RQ4 | 0.44% controlled redundant-variant win rate (95% CI 0–1.02%), N=685 valid controlled pairs. |
| RQ5 | 1.11% controlled format-variant win rate (95% CI 0.42–1.95%), N=719 valid controlled pairs. |
| RQ6 | 50.94% stable same-family preference (95% CI 42.77–58.49%; N=159 stable decisive). Claude 86.21%, GPT-4o-mini 75.76%, and Llama 9.38%; no clear uniform cross-judge preference. |
| RQ7 | Matched retained-decision agreement: baseline 67.66%; DUAL_SWAP 68.37%; difference +0.70 pp (95% CI 0.00–1.58; N=569). Descriptive valid coverage changes from 95.63% to 72.88%, a -22.75 pp trade-off. |

The RQ7 matched retained-decision difference conditions on both strategies
returning valid decisions. Coverage is reported over all planned units. It is
not a causal treatment-effect claim or a claim that mitigation universally
improves reliability.

## 6. Scientific Interpretation and Limitations

- Human preference labels are reference labels, not ground truth.
- RQ3 demonstrates position sensitivity under this frozen protocol; it does
  not by itself prove a universal causal bias mechanism.
- RQ4 is a narrow redundant-length control with factual content preserved. It
  does not establish universal verbosity bias.
- RQ5 is a controlled presentation-format manipulation with semantic
  equivalence checks. It does not establish universal format quality effects.
- RQ6 was separately repaired after the frozen Phase 11 design: the original
  RQ6 remains historical `NOT ESTIMABLE — UNBALANCED_PRESENTATION`, while the
  counterbalanced lineage estimates a matched source-family preference
  association. Its stable-decisive coverage is 33.13%; AB/BA controls
  presentation position but not source/content-quality confounding, so it is
  not causal proof of self-bias.
- RQ7 does not eliminate bias; its coverage cost is part of the result and the
  matched retained-decision difference is non-causal.
- Provider failures, invalid outcomes, exclusions, and incomplete pairings are
  retained in accounting and applied through each metric's stated denominator.

## 7. Final Technical Architecture

The backend is a FastAPI application with SQLAlchemy/PostgreSQL persistence,
controlled planning/execution records, controlled-only analysis adapters, and
a fail-closed controlled-results API. `AnalysisRun` records, manifests,
experimental units, run/pass outcomes, attempts, routing provenance, and
versioned metric contracts provide the technical audit trail.

The React/TypeScript frontend reads the controlled-results API for final
science. The Phase 11 evidence package is an immutable offline reproducibility
snapshot containing indexed data exports, analysis artifacts, provenance,
checksums, and a standard-library verifier.

## 8. Final Frontend State

- `/` opens `/synthesis`, the concise executive synthesis of controlled findings.
- `/controlled-results` is the primary navigation tab and presents the complete
  current controlled RQ1–RQ7 evidence.
- Leaderboard content is historical/exploratory, not final controlled evidence.
- Diagnostics are legacy/exploratory telemetry.
- Qualitative Explorer supports historical qualitative interpretation.
- Live Sandbox is demo-only and disabled by default; it is separated from
  final controlled evidence.

## 9. Final Evidence and Reproducibility

The authoritative evidence package is
[`evidence/final/phase11/`](evidence/final/phase11/). Its key identifiers are:

- DatasetVersion: `2f8c7bba-08b1-4d8b-8b0e-b564e8a61886`
- Dataset SHA-256: `b2fff1524b199fb2d302b7c4ebd752a9a47d32bab68a232ab06b7b1e07fa1510`
- Phase 11 root digest:
  `f1a1d6ffcb6f6fd5a5dd48f7b51a731d6b765a68ff76501bf6c0ef356e53ce13`
- Final technical release tag: `final-technical-cleanup-v1`
- Professional repository release tag: `final-professional-repository-v1`

Phase 10 produced the final offline analysis, including tables, charts,
metrics, and provenance. Phase 11 froze those outputs with the controlled
records, traceability indexes, audited historical isolation, checksum inventory,
and canonical database snapshot. Verify the package offline with
`python evidence/final/phase11/VERIFY_PACKAGE.py`.

The later RQ6 lineage is deliberately not inserted into the immutable Phase 11
package. Its permanent addendum is
[`evidence/final/rq6_counterbalanced/`](evidence/final/rq6_counterbalanced/):
the deterministic AB/BA selection manifest is retained alongside a compact
provenance record that identifies the Experiment, manifest hash, run ledger,
and canonical completed AnalysisRun.

The additive current release is
[`evidence/final/research_release_v2/`](evidence/final/research_release_v2/).
It pins the corrected RQ2/RQ3/RQ4/RQ5/RQ7 analyses, the counterbalanced RQ6
analysis, a physical PostgreSQL custom-format snapshot, `pg_restore --list`, a
disposable-database restore/read test, checksums, and an offline verifier. It
does not modify or reseal Phase 11.

## 10. Important Historical Repairs

The final evidence is accompanied by concise provenance for the repairs that
materially affected scientific validity:

- A real-provider pilot validated the transport/provenance path while remaining
  isolated from final science.
- Controlled RQ4/RQ5 variant materialization defects were identified and
  corrected before final evidence was accepted.
- Pre-fix RQ5 runs were retained in a superseded audit history and excluded
  from the final RQ5 analysis.
- Idempotency, attempt lineage, retry, and terminal-outcome accounting were
  hardened so retries do not become new scientific repetitions.
- Final reconciliation accounted for all units and pass slots before the
  evidence package was frozen.

## 11. Final Validation State

Final cleanup and release validation used no provider calls. The recorded
provider-free backend safety, methodology, analysis, integration, recovery,
health-sanitization, no-data contract, and evidence tests passed; frontend
tests and the production typecheck/build passed. The Phase 11 verifier passed
and its root digest remained unchanged.

The final release workflow maintains a clean working tree before each release
tag. The immutable package, its verifier, separate RQ6 addendum, and the
canonical Phase 11 database snapshot are preserved.

## 12. Current Final Project Status

| Area | Status |
| --- | --- |
| Research implementation | COMPLETE |
| Controlled experiment | COMPLETE |
| Scientific analysis | COMPLETE |
| Frozen evidence | COMPLETE |
| Backend | COMPLETE |
| Frontend | COMPLETE |
| Repository cleanup | COMPLETE |
| README | COMPLETE |
| Academic thesis and defense slides | TO BE PREPARED SEPARATELY |
