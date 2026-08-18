"""Frozen retry, ambiguity, and scientific-failure policy."""
from __future__ import annotations
from dataclasses import dataclass

RETRY_POLICY_VERSION = "controlled-retry-v2"
FAILURE_POLICY_VERSION = "controlled-failure-v2"
PASS_STATES = frozenset({"PENDING", "IN_PROGRESS", "SUCCEEDED", "FAILED_RETRYABLE", "FAILED_FINAL", "AMBIGUOUS"})

@dataclass(frozen=True)
class RetryRule:
    retryable: bool
    max_retries: int
    backoff_seconds: tuple[int, ...] = ()

RETRY_RULES = {
    # The tuple is the scheduler backoff plan in seconds.  The executor records
    # it, but deliberately does not sleep while holding a database transaction.
    "RATE_LIMIT": RetryRule(True, 2, (2, 8)),
    "HTTP_5XX": RetryRule(True, 2, (2, 8)),
    "CONNECTION": RetryRule(True, 2, (2, 8)),
    "TIMEOUT": RetryRule(True, 1, (5,)),
    "INVALID_RESPONSE": RetryRule(False, 0),
    "SCHEMA_INVALID": RetryRule(False, 0),
    "REFUSAL": RetryRule(False, 0),
    "AUTH": RetryRule(False, 0),
    "UNSUPPORTED_MODEL": RetryRule(False, 0),
    "UNSUPPORTED_PARAMETER": RetryRule(False, 0),
    "CONFIGURATION": RetryRule(False, 0),
    "AMBIGUOUS": RetryRule(False, 0),
}

def retry_rule(category: str) -> RetryRule:
    return RETRY_RULES.get(category, RETRY_RULES["CONFIGURATION"])

def terminal_state(category: str, retry_count: int) -> str:
    rule = retry_rule(category)
    return "FAILED_RETRYABLE" if rule.retryable and retry_count < rule.max_retries else "FAILED_FINAL"


def next_backoff_seconds(category: str, retry_count: int) -> int | None:
    """Return the backoff before retry number ``retry_count + 1``.

    This is a policy value only; workers/schedulers must wait outside their
    persistence transaction.  A retry retains its original scientific pass,
    unit, and RQ2 repetition index.
    """
    rule = retry_rule(category)
    return rule.backoff_seconds[retry_count] if retry_count < len(rule.backoff_seconds) else None

# TIE is scientifically valid. All operational failures are reported but only
# decisive/valid-label denominators include ANSWER_A/ANSWER_B/TIE.
SCIENTIFICALLY_VALID = frozenset({"ANSWER_A", "ANSWER_B", "TIE"})
OPERATIONAL_FAILURES = frozenset({"UNKNOWN", "INVALID_RESPONSE", "API_ERROR", "TIMEOUT", "REFUSAL", "MISSING_PASS", "AMBIGUOUS"})


def outcome_semantics(outcome: str | None) -> dict[str, object]:
    """Shared runner/metric meaning for every persisted outcome."""
    normalized = outcome or "MISSING_PASS"
    if normalized in SCIENTIFICALLY_VALID:
        return {"scientifically_valid": True, "included_in_denominator": True, "retryable": False, "excluded_reason": None}
    category = {"API_ERROR": "CONNECTION", "TIMEOUT": "TIMEOUT", "INVALID_RESPONSE": "INVALID_RESPONSE", "REFUSAL": "REFUSAL", "AMBIGUOUS": "AMBIGUOUS"}.get(normalized, "CONFIGURATION")
    return {"scientifically_valid": False, "included_in_denominator": False, "retryable": retry_rule(category).retryable, "excluded_reason": normalized}
