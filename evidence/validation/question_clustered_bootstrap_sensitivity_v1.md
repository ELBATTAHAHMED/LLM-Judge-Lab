# Current CI vs Question-Clustered Bootstrap CI

> Sensitivity/validation analysis only. This report does not replace frozen confidence intervals or authoritative AnalysisRuns.

Method: 10,000 deterministic percentile-bootstrap replicates (seed `20260912`), resampling original MT-Bench question IDs and retaining every eligible observation from each sampled question.

| Metric | Current 95% CI | Question-clustered 95% CI | Width change | Null status | Interpretation |
| --- | ---: | ---: | ---: | --- | --- |
| `RQ1.exact_agreement` | 55.70% to 62.69% | 55.18% to 63.01% | wider by 0.84 pp | descriptive; no tested null | unchanged |
| `RQ1.cohens_kappa` | 0.2698 to 0.3758 | 0.2589 to 0.3845 | wider by 0.0196 | outside → outside | unchanged |
| `RQ2.strict_complete_repetition_consistency` | 96.00% to 97.03% | 95.95% to 97.09% | wider by 0.10 pp | descriptive; no tested null | unchanged |
| `RQ2.conditional_returned_judgment_consistency` | 95.79% to 96.81% | 95.73% to 96.89% | wider by 0.14 pp | descriptive; no tested null | unchanged |
| `RQ3.paired_decisive_flip_rate` | 14.39% to 20.58% | 13.85% to 21.34% | wider by 1.29 pp | outside → outside | unchanged |
| `RQ4.variant_win_rate` | 0.00% to 0.00% | 0.00% to 0.00% | unchanged | inside → inside | unchanged |
| `RQ5.variant_win_rate` | 0.00% to 0.00% | 0.00% to 0.00% | unchanged | inside → inside | unchanged |
| `RQ6.stable_same_family_preference` | 42.77% to 58.49% | 42.47% to 59.70% | wider by 1.51 pp | inside → inside | unchanged |
| `RQ7_PRIMARY.agreement_delta` | -0.17% to 1.68% | -0.18% to 1.62% | narrower by 0.04 pp | inside → inside | unchanged |
| `RQ7_PRIMARY.coverage_delta` | not reported | -24.62% to -17.64% | not comparable | clustered null outside; no official CI | unchanged |
| `RQ7_SECONDARY.agreement` | 69.24% to 74.49% | 68.08% to 75.34% | wider by 2.01 pp | descriptive; no tested null | unchanged |
| `RQ7_SECONDARY.coverage` | 67.54% to 72.13% | 66.95% to 72.76% | wider by 1.21 pp | descriptive; no tested null | unchanged |
| `RQ7_SECONDARY.matched_delta` | 4.16% to 5.89% | 4.02% to 6.04% | wider by 0.29 pp | outside → outside | unchanged |

## Interpretation

The clustering concern affects interval width to different degrees because the number of observations contributed by each question is uneven and multiple judges, turns, repetitions, swaps, or pairs can share a question. Point estimates and eligibility rules are unchanged.

No included metric changed whether its relevant null value was inside or outside the interval. The substantive scientific conclusions therefore remain unchanged in this sensitivity analysis.

RQ7 Primary coverage delta previously had no official confidence interval. Its clustered interval is reported here only to evaluate uncertainty around the existing descriptive coverage trade-off; it is not an official replacement interval.

Multi-Judge remains a secondary/exploratory mitigation analysis with its own retained population and comparator. Its clustered interval must not be ranked directly against DUAL_SWAP.
