# LLM-as-a-Judge Reliability Lab: Final Technical and Scientific Report

## 1. Project Overview

**LLM-as-a-Judge Reliability Lab: Measuring and Mitigating Biases in Automatic
Evaluation of Generated Responses** is a reproducible full-stack research
system for studying pairwise LLM judgments. Its final contribution is a
controlled, provenance-preserving evaluation of alignment with human preference
reference labels, judgment consistency, presentation sensitivity, narrowly
defined counterfactual effects, and two complementary RQ7 mitigation families:
within-judge DUAL_SWAP filtering and cross-judge Multi-Judge Consensus.

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

The additive Multi-Judge Consensus experiment evaluates a separate RQ7
cross-judge aggregation mitigation on 1,611 eligible canonical human-reference
answer pairs. Its four judges are GPT-4o-mini, Claude 3 Haiku, DeepSeek Chat,
and Llama 3.3 70B. It is an official **SECONDARY** RQ7 result; DUAL_SWAP
remains the primary RQ7 mitigation. The current additive
`research_release_v3` snapshot contains 14 AnalysisRuns, including the
Multi-Judge AnalysisRun `fc40faf1-b886-42f8-8faf-a616f61f3107`; it preserves,
rather than changes, immutable Phase 11 and `research_release_v2`.
Individual judges showed heterogeneous reliability and position sensitivity, so
cross-judge aggregation was evaluated as a separate mitigation family rather
than as a replacement for DUAL_SWAP.

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

The separate Multi-Judge execution planned 6,444 scientific passes (four per
eligible pair): 6,390 completed, 52 terminal failures, and 2 ambiguous slots,
with 0 pending. Its durable ledger records 6,543 attempts and 99 retries. The
reconciled actual spend was $1.46018394 under a $2.50 hard cap; retries and
failures remain in the ledger rather than becoming extra scientific passes.

## 5. Final Scientific Results

| RQ | Authoritative final result |
| --- | --- |
| RQ1 | 58.44% agreement with human preference reference labels (95% CI 55.06–61.95%), Cohen's kappa 0.3121, N=770. |
| RQ2 | Primary strict complete-repetition consistency: 96.74% (95% CI 96.22–97.23%), N=1,428 all-valid groups. Conditional returned-judgment sensitivity: 96.56%, N=1,474. No final temperature comparison is estimable. |
| RQ3 | 16.70% paired decisive flip rate (95% CI 13.76–19.82%), N=545 decisive pairs; 24.87% all-paired disagreement, N=756 complete pairs. |
| RQ4 | 0.44% controlled redundant-variant win rate (95% CI 0–1.02%), N=685 valid controlled pairs. |
| RQ5 | 1.11% controlled format-variant win rate (95% CI 0.42–1.95%), N=719 valid controlled pairs. |
| RQ6 | 50.94% pooled stable same-family association (81/159; 95% CI 42.77–58.49%; coverage 33.13%). Claude 86.21%, GPT-4o-mini 75.76%, and Llama 9.38%; no clear uniform cross-judge preference. |
| RQ7 | **Primary DUAL_SWAP:** baseline 67.66%; DUAL_SWAP 68.37%; matched difference +0.70 pp (95% CI 0.00–1.58; N=569), with descriptive coverage 95.63% to 72.88% (-22.75 pp). **Secondary Multi-Judge Consensus:** 795/1,125 = 70.67% versus a 65.80% equal-weight individual-judge comparator; matched delta +4.87 pp (95% CI +4.02 to +5.73 pp), coverage 69.83% of 1,611 planned pairs. |

The DUAL_SWAP matched retained-decision difference conditions on valid baseline
and DUAL_SWAP decisions. Multi-Judge uses its own same-retained-pairs
equal-weight individual-judge comparator. Coverage is reported over each
strategy's planned units. Neither result is a causal treatment-effect claim or
a claim that mitigation universally improves reliability.

## 6. RQ7 Mitigation Strategies

RQ7 evaluates two complementary operating points, not a competition between
methods. **DUAL_SWAP (PRIMARY)** is a within-judge presentation-consistency
filter: it retains decisions stable under counterbalanced presentation and has a
small matched agreement change (+0.70 pp; 95% CI 0.00–1.58 pp; N=569) alongside
a descriptive coverage reduction from 95.63% to 72.88%. **Multi-Judge
Consensus (SECONDARY)** is cross-judge aggregation: under its own frozen
equal-weight individual-judge comparator, it increases agreement with human
preference reference labels by +4.87 pp (95% CI +4.02 to +5.73 pp) on 1,125
retained pairs, with 69.83% planned-pair coverage.

### Frozen Multi-Judge protocol

The frozen `multi-judge-consensus-v1` protocol evaluates each canonical pair
once with each of GPT-4o-mini, Claude 3 Haiku, DeepSeek Chat, and Llama 3.3
70B. The deterministic schedule uses exact 2 AB / 2 BA presentation per pair
(seed 20260823). Each judge's vote is mapped back to the ORIGINAL answer
identity before aggregation. `ANSWER_1`, `ANSWER_2`, and `TIE` are valid
three-class votes; TIE is a genuine third class, not missingness or abstention.
Operational failures produce no vote.

Primary consensus requires all four votes to be valid and a 3-of-4 or 4-of-4
agreement on the same three-class label: 4–0 and 3–1 produce consensus, whereas
2–2 and 2–1–1 do not. Of 1,611 eligible pairs, 1,473 had four valid votes and
1,125 met this strict consensus rule. The analysis uses canonical pair as the
unit and a nonparametric percentile bootstrap (10,000 resamples, 95% CI,
seed 20260823).

### Interpretation, robustness, and comparison boundary

The primary Multi-Judge result is 795 / 1,125 = 70.67% agreement, compared
with 65.80% for the equal-weight individual-judge baseline on the same retained
pairs. Sensitivity analyses are secondary: three-valid consensus gave +1.10 pp
with a CI spanning zero; leave-one-out deltas were +4.71 pp (omit GPT), +3.46
pp (omit Claude), +4.39 pp (omit DeepSeek), and +4.90 pp (omit Llama);
decisive-only was +5.56 pp; and strict unanimity gave 0.00 pp with 37.00%
coverage. All eight category descriptive deltas were positive. The direction
therefore did not appear to depend on one judge, but the weaker three-valid
sensitivity and unanimity coverage loss remain important qualifications.

A direct DUAL_SWAP-versus-Multi-Judge comparison is **not defensible**.
DUAL_SWAP uses canonical answer pair × judge units, whereas Multi-Judge uses
canonical answer-pair units. Their retained populations, comparators, and
estimands differ, so the +4.87 pp and +0.70 pp estimates must not be ranked or
treated as head-to-head effects.

## 7. Scientific Interpretation and Limitations

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
- RQ7 does not eliminate bias. DUAL_SWAP provides a within-judge
  stability/retention control with a coverage trade-off; Multi-Judge Consensus
  improves agreement on its retained cases relative to its own comparator while
  also abstaining from uncovered pairs. Stability alone does not guarantee
  alignment with human preference reference labels.
- Provider failures, invalid outcomes, exclusions, and incomplete pairings are
  retained in accounting and applied through each metric's stated denominator.

## 8. Final Technical Architecture

The backend is a FastAPI application with SQLAlchemy/PostgreSQL persistence,
controlled planning/execution records, controlled-only analysis adapters, and
a fail-closed controlled-results API. `AnalysisRun` records, manifests,
experimental units, run/pass outcomes, attempts, routing provenance, and
versioned metric contracts provide the technical audit trail.

The React/TypeScript frontend reads the controlled-results API for final
science. The Phase 11 evidence package is an immutable offline reproducibility
snapshot containing indexed data exports, analysis artifacts, provenance,
checksums, and a standard-library verifier.

## 9. Final Frontend State

- `/` opens `/leaderboard`; the controlled synthesis remains available at `/synthesis`.
- `/controlled-results` is the primary navigation tab and presents the complete
  current controlled RQ1–RQ7 evidence.
- Leaderboard content is historical/exploratory, not final controlled evidence.
- Diagnostics are legacy/exploratory telemetry.
- Qualitative Explorer supports historical qualitative interpretation.
- Live Sandbox is demo-only and disabled by default; it is separated from
  final controlled evidence.

## 10. Final Evidence and Reproducibility

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

[`evidence/final/research_release_v2/`](evidence/final/research_release_v2/)
remains immutable. It pins the corrected RQ2/RQ3/RQ4/RQ5/RQ7 analyses, the
counterbalanced RQ6 analysis, a PostgreSQL custom-format snapshot,
`pg_restore --list`, a disposable restore/read test, checksums, and an offline
verifier; it does not modify or reseal Phase 11.

The Multi-Judge package is
[`evidence/final/multijudge_consensus_v1/`](evidence/final/multijudge_consensus_v1/).
It identifies protocol `multi-judge-consensus-v1`, analysis
`multi-judge-consensus-analysis-v1`, AnalysisRun
`fc40faf1-b886-42f8-8faf-a616f61f3107`, and package root digest
`126470152305268908e5685df9ff52ad5a2b6f9266e828201a1c69faac710da1`.
The package captures the frozen protocol, deterministic manifest, exact AB/BA
schedule, PostgreSQL durable execution ledger, retry/idempotency protections,
cost ledger, provider-free analysis, and offline verifier.

[`evidence/final/research_release_v3/`](evidence/final/research_release_v3/)
is the current additive release. Its PostgreSQL custom-format snapshot contains
14 AnalysisRuns and has release root digest
`8d24123e28e5df2ca0401fd4f57944c7d0dd8844e798f2f0ed8b6b2280bae710`.
It was successfully validated through a disposable restore and controlled API
reconciliation. Release v3 is additive: Phase 11 and release v2 remain
immutable. The Phase 11, release-v2, Multi-Judge-package, and release-v3
verifiers are retained as independent provider-free checks.

## 11. Important Historical Repairs

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

## 12. Final Validation State

Final cleanup and release validation used no provider calls. The recorded
provider-free backend safety, methodology, analysis, integration, recovery,
health-sanitization, no-data contract, and evidence tests passed; frontend
tests and the production typecheck/build passed. The Phase 11, release-v2,
Multi-Judge-package, and release-v3 verifiers passed; the Phase 11 root digest
remained unchanged.

The final release workflow maintains a clean working tree before each release
tag. The immutable Phase 11 package, release-v2 snapshot, separate RQ6
addendum, Multi-Judge package, and additive release-v3 snapshot are preserved.

## 13. Current Final Project Status

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
