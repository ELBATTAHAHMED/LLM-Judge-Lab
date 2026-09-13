# Study methodology and inference provenance

## Status, scope, and source hierarchy

This is a methodology record for the current source-corrected study. It is a
documentation aid, not a replacement for any frozen artifact, AnalysisRun,
confidence interval, or result. Concrete statements below are traced to the
committed source files and manifests named in each section.

The current controlled-study input is
`source-corrected-controlled-study-v1`. Its canonical manifest is
`data/canonical/source_corrected_study_v1.json`; the manifest contains 1,568
logical reference records and is checksum-validated by
`backend/data/canonical.py`. The immutable raw human-judgment snapshot is
`data/human_judgment.jsonl` (3,355 rows; SHA-256
`48f627d9a5ebb529869d5d12953e4b309dd81f9bfab034a92a0ed902d84fa5a4`),
recorded in `data/metadata/raw_human_judgment_snapshot_v1.json` as the
`lmsys/mt_bench_human_judgments` source snapshot.

The study frame contains 80 distinct upstream MT-Bench questions (question IDs
81–160). Each has turn 1 and turn 2, yielding 160 turn-level prompt records;
these must not be described as 160 distinct questions. The source-corrected
full-population result artifact is
`evidence/remediation/source_corrected_complete_case_full_population_analysis_v2.json`.

## Human preference reference labels and answer identity

### Source and normalization

Each canonical record is keyed by upstream `(question_id, turn)`, two source
model identities, and SHA-256 hashes of their exact answer texts. The raw
source records expose `model_a`, `model_b`, and `winner`. During canonical
validation, `backend/data/canonical.py` normalizes the upstream winner as:

| Upstream `winner` | Canonical label |
| --- | --- |
| `model_a` | `ANSWER_A` |
| `model_b` | `ANSWER_B` |
| `tie` | `TIE` |

`ANSWER_A` and `ANSWER_B` therefore identify the ordered answers in the
canonical record; they do not identify a model family or a displayed UI slot.
The validator accepts either an exact source-order human row or a reversed
source-order row after swapping `ANSWER_A` and `ANSWER_B`; `TIE` is invariant
under reversal. It rejects missing, ambiguous, or hash-mismatched prompt and
answer identities. The source alias `vicuna-13b-v1.2` is normalized to
`vicuna-13b` before lookup.

For fresh database construction, the exact source text is resolved by
`(question_id, turn, model, SHA-256)`, never database insertion order. A
canonical `TIE` is persisted with no winner answer ID; a non-tie label is
persisted with the exact canonical answer ID that won. The two forensic turn-2
disambiguations are explicitly committed in the canonical/frozen
reconciliation lineage; their labels are retained from that committed lineage
rather than inferred from a different raw row.

The canonical dataset contains 894 `ANSWER_A`, 305 `ANSWER_B`, and 369 `TIE`
reference labels. These are **human preference reference labels**: they are a
traceable comparison target for the observed source answer pair, not objective
quality, factual correctness, or absolute ground truth.

### Judge labels and eligibility

The LLM judge output space is separately normalized as `ANSWER_A`, `ANSWER_B`,
`TIE`, `UNKNOWN`, `INVALID_RESPONSE`, `API_ERROR`, `TIMEOUT`, `REFUSAL`, or a
missing/ambiguous state. Only `ANSWER_A`, `ANSWER_B`, and `TIE` are
scientifically valid three-class labels. A valid displayed A/B decision is
mapped through the persisted presented answer IDs back to the original
canonical answer identity before analyses compare it with the human reference.
Raw displayed A/B labels are never compared directly across a swapped
presentation.

Estimator eligibility is deliberately specific rather than global:

- RQ1 requires both a valid human reference and a valid three-class judge
  label.
- RQ2 operates on exact repetition groups and distinguishes strict all-five
  valid groups from the conditional returned-judgment sensitivity estimand.
- RQ3 requires a complete AB/BA pair; the decisive-flip metric additionally
  requires two decisive mapped outcomes.
- RQ4 and RQ5 require a complete, validated matched original/variant pair.
- RQ6 requires its counterbalanced source-family eligibility and a stable
  decisive AB/BA outcome for its primary rate.
- RQ7 Primary keeps baseline and both DUAL_SWAP passes linked; its matched
  agreement delta requires valid human, baseline, and stable DUAL_SWAP labels.
- RQ7 Secondary requires the documented strict four-valid-vote consensus rule
  for a covered consensus decision.

Thus ties are retained as valid labels where the estimator admits them; they
are not silently converted into either answer, missingness, or half a win.

## Actual judge and source-model identifiers

The following are the exact configured **judge** identifiers in
`backend/core/model_registry.py` and the source-corrected execution manifest.
They must not be conflated with the historical candidate-answer model names.

| Judge identifier | API provider | Requested/provider model identifier | Frozen route |
| --- | --- | --- | --- |
| `gpt-4o-mini` | `OPENAI` | `gpt-4o-mini` | `OPENAI_DIRECT` |
| `anthropic/claude-3-haiku` | `OPENROUTER` | `anthropic/claude-3-haiku` | `amazon-bedrock` |
| `deepseek/deepseek-chat` | `OPENROUTER` | `deepseek/deepseek-chat` | `streamlake` |
| `meta-llama/llama-3.3-70b-instruct` | `OPENROUTER` | `meta-llama/llama-3.3-70b-instruct` | `deepinfra/turbo` |

The frozen routing policy is `controlled-routing-v1`, with fingerprint
`bf8d0d1ef228f60e07ceff2e1da43eeefe8ae5538d439b5d9a4c325294b7030b`.
It forbids fallback routing and requires routing provenance validation. The
stored execution provenance records requested, effective, and observed
upstream model/provider metadata when returned by the provider.

The canonical **candidate-answer** model names are a different historical
source dimension: `alpaca-13b`, `claude-v1`, `gpt-3.5-turbo`, `gpt-4`,
`llama-13b`, and `vicuna-13b`. Consequently, for example, `claude-v1` is a
candidate-answer source label, whereas `anthropic/claude-3-haiku` is the
configured Claude-family judge identifier.

RQ6 uses only `gpt-4o-mini`, `anthropic/claude-3-haiku`, and
`meta-llama/llama-3.3-70b-instruct`; `deepseek/deepseek-chat` is excluded from
that experiment because no source-known candidate answer belongs to its judge
family. RQ7 Secondary/Multi-Judge uses all four listed judge identifiers.

## Controlled inference contract

### Prompt and output contract

The frozen prompt template is `controlled-judge-pairwise-v1`, SHA-256
`e1d041bd6a1ec4f27efe6a3377d98ec0321af02b59ee9abedf64bf349ac9b299`
(`backend/evaluation/prompts.py`). It consists of:

1. A system instruction to act as an impartial evaluator, evaluate only the
   question and two answer texts, avoid inferring authorship/condition/intent,
   and treat A and B symmetrically.
2. A user message containing `Question`, `Answer A`, and `Answer B`, followed
   by the requirement to return JSON only.

The required JSON object has exactly `verdict`, `criteria_scores`,
`confidence`, and `explanation`. `verdict` is one of `ANSWER_A`, `ANSWER_B`,
`TIE`, or `UNKNOWN`; the five criterion scores are strict integers 1–5 for
correctness, relevance, completeness, clarity, and safety; confidence is a
self-reported finite number in [0, 1]; and explanation is nonempty text.
Self-reported confidence is stored as a judge output, not treated as calibrated
probability.

The adapter may remove a markdown code fence and isolate an apparent JSON
object from a text response before validation. It then validates the result
strictly with the `ProviderJudgement` schema (`extra="forbid"`). Invalid JSON,
missing fields, wrong types, out-of-range fields, or extra fields produce
`INVALID_RESPONSE`; they are not repaired by heuristic relabeling. `UNKNOWN`
is a valid parsed provider response but is not a valid scientific three-class
decision denominator.

### Settings, repetitions, and seeds

All four-judge Multi-Judge execution manifest requests use temperature `0`,
top-p `1`, maximum output tokens `350`, and no provider request seed. Its
deterministic presentation-assignment and analysis/bootstrap seed is
`20260823`; it is not a provider decoding seed.

The source-corrected controlled manifest preserves the configuration actually
attached to its reusable historical and corrected/recovery pass lineages. Its
populated pass metadata includes temperature `0.0000` or `0.7000`, top-p
`1.0000`, and provider-request seed values of `null`, `42`, or `20260818`.
The non-null request seeds occur for `gpt-4o-mini`; the other configured judge
entries carry no provider seed. Some RQ7 Secondary staging rows in that
source-corrected manifest have blank inference fields because the executed
Multi-Judge manifest is its separate authoritative execution contract.

RQ2 has five planned repetitions per exact fixed-configuration group. A retry
is an operational attempt for the same scientific pass and never creates a new
RQ2 repetition. The project does not make a final temperature-effect claim:
repeatability is evaluated within the persisted identical configuration group.

Analysis/bootstrap seeds are separate from inference settings:

| Analysis | Seed | Resamples / unit |
| --- | ---: | --- |
| Source-corrected full-population RQ1–RQ7 Primary and RQ6 | `20260818` | 10,000 percentile-bootstrap resamples at the existing estimator-specific unit |
| RQ7 Secondary/Multi-Judge | `20260823` | 10,000 pair-level nonparametric percentile-bootstrap resamples |
| Phase-2 question-clustered sensitivity analysis | `20260912` | 10,000 original-question-cluster resamples |

### Retry, failure, and recovery policy

The frozen retry policy is `controlled-retry-v2`; its paired failure policy is
`controlled-failure-v2` (`backend/evaluation/retry_policy.py`). Rate limits,
HTTP/temporary 5xx, and connection failures may be retried at most twice with
2- and 8-second backoffs. A timeout may be retried once with a 5-second
backoff. Invalid/schema-invalid responses, refusals, authentication/configuration
failures, provenance mismatches, budget blocks, unsupported models/parameters,
and ambiguous attempts are terminal under this policy.

Attempts are persisted before sending. A successful scientific pass is never
silently duplicated; an in-progress or ambiguous attempt after a restart needs
explicit resolution. Recovery was bounded and preserved scientific inputs,
identity, and provenance. It did not invent outputs, relax parsing, substitute
models, or change the source reference labels.

## Missing observations and complete cases

Fourteen terminal Claude observations remained unavailable after bounded
recovery. The authoritative source-corrected analysis records that their
provider response identifiers were retained but raw rejected response bodies
were not persisted, so scientifically defensible offline re-parsing is not
possible. These observations were neither fabricated nor imputed.

The missingness is documented as Claude/OpenRouter/Amazon-Bedrock specific and
concentrated in a small subset of questions, turns, and categories. Analyses
therefore report estimator-specific complete-case populations where required;
they do **not** claim that missingness is MCAR or MAR. Linked analyses exclude
an incomplete linked unit under their stated rule rather than filling a missing
pass. Operational accounting remains separate from scientific denominators.

## Dependence and uncertainty sensitivity

The official frozen intervals retain their existing estimator-specific
resampling units. The Phase-2 validation added a separate, non-authoritative
question-clustered bootstrap sensitivity analysis at
`evidence/validation/question_clustered_bootstrap_sensitivity_v1.json`.

It samples the original MT-Bench question ID, not the turn-level prompt, with
replacement while retaining all eligible observations from each sampled
question. Thus turns, judges, repetitions, swaps, variants, and matched pairs
derived from the same question remain together. This addresses the plausible
within-question dependence that observation-level resampling does not model.

The sensitivity analysis uses 10,000 deterministic replicates (seed
`20260912`), reports valid and non-estimable replicate counts, and does not
replace official CIs. All included metrics had 10,000 valid and zero
non-estimable replicates; no relevant null-value status or substantive
scientific conclusion changed.

## Synchronization status

The following locations have been synchronized against this methodology
record. They retain the distinction between official intervals and the
question-clustered sensitivity analysis:

- `README.md` and `PROJECT_FINAL_TECHNICAL_AND_SCIENTIFIC_REPORT.md`: concise
  methodology, exact judge identifiers, provenance, missingness, and the
  clustered-bootstrap qualification.
- `report/chapters/`: aligned methods, limitations, and uncertainty wording
  without replacing official CIs.
- `frontend/src/pages/SynthesisPage.tsx`,
  `frontend/src/pages/ControlledResultsPage.tsx`, and related result copy:
  aligned explanatory text only; API values remain unchanged.
- Any legacy/historical analysis text that uses `gpt-4o-mini` as a generic
  label must distinguish that judge identifier from historical candidate-answer
  source models, and must avoid unqualified “ground truth”, causal self-bias,
  or universal temperature-effect language.

## Evidence locations

- Dataset and source validation: `backend/data/canonical.py`,
  `data/metadata/CANONICAL_SOURCE_DATA.md`, and
  `data/metadata/raw_human_judgment_snapshot_v1.json`.
- Prompt, model, route, parser, and retry contracts:
  `backend/evaluation/prompts.py`, `backend/core/model_registry.py`,
  `backend/evaluation/routing_config.json`, `backend/evaluation/engine.py`,
  and `backend/evaluation/retry_policy.py`.
- Source-corrected execution and missingness lineage:
  `evidence/remediation/controlled_source_text_corrected_execution_manifest_v1.json`
  and `backend/analysis/source_corrected_complete_case.py`.
- RQ6 and Multi-Judge special protocols:
  `evidence/final/rq6_counterbalanced/selection_manifest.json`,
  `evidence/multijudge_consensus/protocol_v1.json`, and
  `evidence/multijudge_consensus/execution_manifest_v1.json`.
- Phase-2 uncertainty sensitivity:
  `backend/analysis/question_clustered_bootstrap.py` and
  `evidence/validation/question_clustered_bootstrap_sensitivity_v1.json`.
