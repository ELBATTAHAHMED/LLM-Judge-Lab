# Research Scope: Three Main Questions

## Status and authority

This document defines the Phase-1 scientific framing for the project. It
changes neither the experiment design nor the authoritative evidence. The
internal identifiers `RQ1` through `RQ7`, their AnalysisRuns, estimators,
eligibility rules, denominators, confidence intervals, datasets, database
records, API contracts, and frozen evidence remain unchanged.

The existing source-corrected final evidence remains the authority for all
reported results. This document only specifies how those existing analyses are
grouped at the higher level of the research narrative.

## Main research questions

| Main question | Existing internal analysis | Scientific focus |
| --- | --- | --- |
| **Main Q1 — Human Agreement** | `RQ1` | Agreement of LLM judges with human preference reference labels. These labels remain reference labels, not absolute ground truth. |
| **Main Q2 — Stability** | `RQ2` and `RQ3` | Stability of LLM judging under two distinct conditions: repeated fixed-condition evaluation (`RQ2`) and answer-order inversion (`RQ3`). |
| **Main Q3 — Mitigation** | `RQ7` Primary / `DUAL_SWAP` | The mitigation operating point, interpreted jointly through agreement, coverage, and the agreement–coverage trade-off. |

`RQ2` and `RQ3` are not merged scientifically or operationally. They retain
their separate estimands, populations, metrics, and internal identifiers. Main
Q2 is only their shared higher-level framing.

## Secondary and exploratory analyses

| Scope | Existing internal analysis | Role in the three-question framing |
| --- | --- | --- |
| Secondary | `RQ4` | Controlled redundant-length treatment analysis. |
| Secondary | `RQ5` | Controlled presentation-format treatment analysis. |
| Exploratory | `RQ6` | Counterbalanced source-family association analysis. It does not establish causal self-preference. |
| Secondary/exploratory mitigation | `RQ7` Secondary / Multi-Judge Consensus | Cross-judge aggregation analysis, retained as visible and scientifically useful supporting mitigation evidence. |

## Mitigation boundary

`DUAL_SWAP` remains the primary mitigation result because it is the mitigation
analysis assigned to Main Q3. Its interpretation must jointly report agreement,
coverage, and their trade-off rather than agreement alone.

Multi-Judge Consensus remains a valid secondary/exploratory mitigation
analysis. It uses a different retained population and an equal-weight
individual-judge comparator. It must not be directly ranked against, or
claimed superior/inferior to, `DUAL_SWAP`; the two results have different
estimands and comparators.

## Synchronization status

The three-question framing has been propagated to the mutable presentation and
documentation layers while preserving the internal `RQ1`–`RQ7` evidence model:

- `README.md`: research-question table, results narrative, and interpretation
  boundaries.
- `PROJECT_FINAL_TECHNICAL_AND_SCIENTIFIC_REPORT.md`: research scope and
  results framing.
- `report/chapters/`: introduction, methods, results, discussion, and summary
  framing in the generated academic documents.
- `frontend/src/pages/SynthesisPage.tsx`: executive grouping of findings.
- `frontend/src/pages/ControlledResultsPage.tsx` and
  `frontend/src/components/ControlledEvidencePanel.tsx`: controlled-results
  navigation and explanatory hierarchy.
- `frontend/src/api/finalEvidence.ts` and related frontend tests: display
  labels and interpretations only, without changing the API contract or
  scientific values.

No backend API, database, evidence, estimator, or experiment change was
required for this synchronization.
