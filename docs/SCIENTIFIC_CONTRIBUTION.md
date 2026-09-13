# Scientific Contribution: Human Alignment, Stability, and Mitigation

## Status and authority

This document defines the Phase-4 scientific narrative for the existing
source-corrected study. It does not replace the internal `RQ1`–`RQ7`
identifiers, their estimators, authoritative AnalysisRuns, official confidence
intervals, or frozen evidence. The three-question framing in
`docs/RESEARCH_SCOPE.md` remains the organizing structure.

## Central scientific story

The project evaluates an LLM judge as a measurement instrument along three
connected dimensions: **human alignment**, **stability**, and the
**agreement–coverage trade-off of mitigation**. These dimensions must be read
together. A judge can reproduce its own decision under fixed conditions while
still agreeing only partially with human preference reference labels or
changing its decision when answer order is inverted. Likewise, a mitigation
cannot be assessed through agreement alone if it changes how many observations
receive a usable verdict.

### One-sentence contribution

This project contributes an integrated controlled reliability framework showing
that LLM judges can be highly repeatable without being strongly aligned with
human preference reference labels or fully robust to answer order, and that
mitigation must be assessed jointly through agreement and coverage.

### Short contribution statement

Rather than treating automatic judging as a single accuracy score, the project
connects three complementary measurements in one provenance-controlled study:
agreement with human preference reference labels, stability across repetition
and answer-order inversion, and the operating-point trade-off produced by
mitigation. Its contribution is this integrated measurement perspective and the
reproducible evidence chain supporting it. It does not claim to have invented
repeatability testing, order swapping, consensus voting, or the underlying
statistical methods.

## Three main research questions

1. **Main Q1 — Human Agreement:** To what extent do LLM judges agree with human
   preference reference labels under the controlled study protocol?
2. **Main Q2 — Stability:** How stable are LLM-judge decisions across repeated
   fixed-condition evaluations and answer-order inversion?
3. **Main Q3 — Mitigation:** What agreement–coverage trade-off does the primary
   `DUAL_SWAP` mitigation produce?

The internal analyses remain distinct: Main Q1 maps to `RQ1`; Main Q2 groups,
but does not merge, `RQ2` and `RQ3`; and Main Q3 maps to `RQ7` Primary /
`DUAL_SWAP`.

## Three main findings

### 1. Human alignment is partial

For `RQ1`, LLM-judge decisions agreed with human preference reference labels in
457 of 772 eligible analytical observations: **59.20% agreement**, with
**Cohen's kappa = 0.3230**. This indicates partial alignment under the study
protocol. The source human labels are comparison reference labels, not absolute
ground truth, so the result does not establish an objective accuracy rate.

### 2. Stability is multidimensional

For `RQ2`, fixed-condition repeated evaluations were consistent in **96.53%**
of the strict eligible repetitions. For `RQ3`, however, **17.49%** of decisive
paired comparisons changed their mapped outcome after answer-order inversion.
The two results are not contradictory: they test different perturbations.
High repeatability under an unchanged presentation does not imply strong human
alignment, nor does it imply complete robustness to answer order.

### 3. Mitigation has an agreement–coverage trade-off

For `RQ7` Primary, the matched retained-decision agreement changed from
**67.84%** for the baseline to **68.51%** for `DUAL_SWAP`, a difference of
**+0.67 percentage points**. The official 95% confidence interval for this
difference is **-0.17 to +1.68 percentage points**. At the operating point,
coverage changed from **96.87%** to **75.84%**, a difference of **-21.03
percentage points**. The defensible conclusion is therefore a small, uncertain
agreement change accompanied by a substantial loss of coverage. The evidence
does not justify reducing the result to either “the mitigation works” or “the
mitigation fails.”

## Supporting analyses and their roles

- **`RQ4` — secondary:** a narrow controlled redundant-text treatment. Its
  result must not be generalized to all response length or verbosity effects.
- **`RQ5` — secondary:** a narrow controlled list-prefix/presentation-format
  treatment. Its result must not be generalized to all formatting effects.
- **`RQ6` — exploratory:** a counterbalanced source-family preference
  association. The aggregate result does not establish a causal self-bias
  mechanism, and the judge-level patterns are heterogeneous.
- **`RQ7` Secondary / Multi-Judge — secondary/exploratory mitigation:** strict
  cross-judge aggregation showed a positive matched difference relative to its
  own equal-weight individual-judge comparator on its retained population. It
  remains scientifically useful supporting evidence, but it does not replace
  `DUAL_SWAP` as the primary mitigation analysis.

`DUAL_SWAP` and Multi-Judge answer different questions. `DUAL_SWAP` applies
within-judge presentation-consistency filtering; Multi-Judge applies
cross-judge aggregation. Their populations, comparators, and estimands differ,
so their effect sizes must not be ranked as a direct head-to-head comparison.

## Question-clustered sensitivity analysis

The Phase-2 sensitivity analysis resampled the original MT-Bench question ID as
the clustering unit for 10,000 deterministic bootstrap replicates (seed
`20260912`). Each sampled question carried all of its eligible turns, judges,
repetitions, swaps, and variants, preserving dependence among observations that
originated from the same question. The clustered intervals changed width to
different degrees, but no included metric changed whether its relevant null
value lay inside or outside the interval. The substantive conclusions therefore
remained unchanged.

This sensitivity analysis does **not** replace the official confidence
intervals or authoritative AnalysisRuns. In particular, the clustered interval
for the `RQ7` Primary coverage difference is sensitivity evidence only because
the frozen analysis did not report an official interval for that quantity.

## Defense-ready conclusion

The study does not support a binary claim that LLM judges are reliable or
unreliable. It shows instead that reliability has separable dimensions. The
judges were highly repeatable under fixed conditions, yet their agreement with
human preference reference labels was partial and a meaningful share of
decisive outcomes changed under answer-order inversion. The primary mitigation
produced only a small and uncertain agreement change while substantially
reducing coverage. Consequently, an LLM judge should be reported as a
provenance-controlled measurement instrument whose human alignment, stability,
coverage, failures, and mitigation operating point are all made explicit.

## Interpretation boundaries

The project must not claim that:

- human preference reference labels are absolute ground truth;
- high repeatability establishes human alignment or order robustness;
- answer-order sensitivity identifies a causal internal bias mechanism;
- the narrow `RQ4` or `RQ5` treatments settle general length or formatting
  effects;
- `RQ6` proves self-bias;
- `DUAL_SWAP` eliminates bias or universally improves reliability;
- Multi-Judge is superior to `DUAL_SWAP`, or that their deltas are directly
  comparable;
- consensus output is ground truth or ensembles always outperform individual
  judges.

## Synchronization status

The following mutable presentation layers have been synchronized to the
three-question framing and the Phase-2 sensitivity boundary while preserving
the internal `RQ1`–`RQ7` identifiers:

- `README.md` and `PROJECT_FINAL_TECHNICAL_AND_SCIENTIFIC_REPORT.md`: research
  scope, headline findings, contribution, and limitations.
- `report/chapters/`: the three-question hierarchy, supporting-analysis
  boundaries, and official-versus-sensitivity distinction.
- `frontend/src/pages/SynthesisPage.tsx`,
  `frontend/src/pages/ControlledResultsPage.tsx`, and related presentation
  metadata/tests: display hierarchy and explanatory labels only.
- Historical/exploratory wording in `backend/analysis/latent_quality.py` and
  `backend/analysis/neutralized_scores.py`: retained as historical telemetry,
  not final controlled evidence.

No backend scientific estimator, API schema, database record, dataset,
AnalysisRun, or frozen artifact changed to adopt this narrative.
