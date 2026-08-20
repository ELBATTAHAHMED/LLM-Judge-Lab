# Phase 8.5 frozen execution policies

## Human reference and independence

`unordered-pair-consensus-v1` treats human preferences as reference labels,
not ground truth. The source has no annotator identifier, so reversed rows are
not assumed independent. Consistent unordered duplicates are collapsed into a
single canonical answer-ID orientation. Conflicting winner/tie groups are
excluded. Bootstrap resampling uses these frozen unordered pairs as the
independent unit.

## Retry and failure policy

429, temporary 5xx, network failures, and timeouts are retryable at most two
times with bounded exponential backoff; retries increment `retry_count` and
never `repetition_index`. Invalid structured responses, refusals, and
configuration errors are final unless a documented provider outage is proven.
`UNKNOWN`, invalid response, API error, timeout, and missing pass are reported
separately. Paired RQ3/RQ4/RQ5/RQ7 metrics require both valid required passes;
RQ1/RQ2/RQ6 report coverage and exclude operational failures only from their
explicit valid-label denominator.

## Scope freeze

RQ4 is **Controlled Redundant-Length Effect**: adding duplicate, redundant
length while preserving factual content. It is not a general verbosity claim.
RQ5 is **Controlled Presentation-Format Effect**: syntax/presentation only,
not a general organization or heading-quality claim. RQ7 evaluates exactly one
mitigation: baseline single-pass versus dual-swap, with signed mitigation minus
baseline deltas. Criterion scores are auxiliary provenance metadata, not a
separate thesis outcome.
