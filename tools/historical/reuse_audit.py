"""Read-only Phase 8 reuse-versus-rerun audit.

This module never calls a provider and never promotes legacy evidence.  It
classifies recoverable provenance against the frozen protocol conservatively.
"""
from __future__ import annotations

import csv
from collections import Counter
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
import sys
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy.orm import Session

from backend.core.models import Answer, HumanPreference, JudgeDecision, Prompt  # noqa: E402


class ReuseClass(str, Enum):
    REUSE_AS_DATASET = "REUSE_AS_DATASET"
    REUSE_AS_REFERENCE = "REUSE_AS_REFERENCE"
    REUSE_AS_EXPLORATORY = "REUSE_AS_EXPLORATORY"
    REUSE_FOR_VALIDATION = "REUSE_FOR_VALIDATION"
    FINAL_CONTROLLED_CANDIDATE = "FINAL_CONTROLLED_CANDIDATE"
    NOT_REUSABLE = "NOT_REUSABLE"


class ReasonCode(str, Enum):
    MISSING_PASS_LEVEL_DATA = "MISSING_PASS_LEVEL_DATA"
    MISSING_PRESENTATION_ORDER = "MISSING_PRESENTATION_ORDER"
    MISSING_REPETITION_ID = "MISSING_REPETITION_ID"
    WRONG_GROUPING = "WRONG_GROUPING"
    MISSING_PROVIDER_IDENTITY = "MISSING_PROVIDER_IDENTITY"
    MISSING_EFFECTIVE_MODEL = "MISSING_EFFECTIVE_MODEL"
    MISSING_PROTOCOL_VERSION = "MISSING_PROTOCOL_VERSION"
    MISSING_TEMPLATE_VERSION = "MISSING_TEMPLATE_VERSION"
    NO_DATASET_SNAPSHOT = "NO_DATASET_SNAPSHOT"
    UNCONTROLLED_VARIANT = "UNCONTROLLED_VARIANT"
    SEMANTICALLY_CONFOUNDED = "SEMANTICALLY_CONFOUNDED"
    SOURCE_METADATA_MISSING = "SOURCE_METADATA_MISSING"
    LEGACY_METRIC_ONLY = "LEGACY_METRIC_ONLY"
    LIVE_SANDBOX = "LIVE_SANDBOX"
    MOCK_DATA = "MOCK_DATA"
    INCOMPLETE_PROVENANCE = "INCOMPLETE_PROVENANCE"
    PROTOCOL_MISMATCH = "PROTOCOL_MISMATCH"


FROZEN_DIMENSIONS = ("provider", "effective_model", "protocol_version", "prompt_template_version", "dataset_snapshot", "temperature", "top_p", "seed", "repetition_index")


def historical_decision_reasons(*, calibrated: bool = False, live_sandbox: bool = False) -> tuple[ReasonCode, ...]:
    if live_sandbox:
        return (ReasonCode.LIVE_SANDBOX,)
    reasons = (ReasonCode.MISSING_PROVIDER_IDENTITY, ReasonCode.MISSING_EFFECTIVE_MODEL, ReasonCode.MISSING_PROTOCOL_VERSION, ReasonCode.MISSING_TEMPLATE_VERSION, ReasonCode.NO_DATASET_SNAPSHOT, ReasonCode.MISSING_REPETITION_ID, ReasonCode.INCOMPLETE_PROVENANCE, ReasonCode.PROTOCOL_MISMATCH)
    return reasons + ((ReasonCode.MISSING_PASS_LEVEL_DATA,) if calibrated else ())


def is_exact_frozen_match(provenance: dict[str, object]) -> bool:
    """Partial provenance never qualifies: every frozen dimension must exist."""
    return all(provenance.get(field) not in (None, "") for field in FROZEN_DIMENSIONS)


def classify_historical_decision(*, calibrated: bool, live_sandbox: bool, provenance: dict[str, object]) -> tuple[ReuseClass, tuple[ReasonCode, ...]]:
    if live_sandbox:
        return ReuseClass.REUSE_AS_EXPLORATORY, historical_decision_reasons(live_sandbox=True)
    if is_exact_frozen_match(provenance) and not calibrated:
        return ReuseClass.FINAL_CONTROLLED_CANDIDATE, ()
    return ReuseClass.REUSE_AS_EXPLORATORY, historical_decision_reasons(calibrated=calibrated)


def audit_csv(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    fields = set(rows[0]) if rows else set()
    if path.name.startswith("stochastic_consistency_real"):
        exact_pair = {"answer_a_id", "answer_b_id"} <= fields
        temperatures = sorted({row.get("temperature", "") for row in rows})
        return {"count": len(rows), "classification": ReuseClass.REUSE_AS_EXPLORATORY.value, "reasons": [ReasonCode.WRONG_GROUPING.value, ReasonCode.MISSING_REPETITION_ID.value, ReasonCode.INCOMPLETE_PROVENANCE.value], "exact_pair_groups": exact_pair, "temperatures": temperatures}
    if path.name == "perturbation_test_results.csv":
        return {"count": len(rows), "classification": ReuseClass.REUSE_AS_EXPLORATORY.value, "reasons": [ReasonCode.UNCONTROLLED_VARIANT.value, ReasonCode.SEMANTICALLY_CONFOUNDED.value, ReasonCode.MISSING_PRESENTATION_ORDER.value], "variant_types": sorted({row.get("perturbation_type", "") for row in rows})}
    return {"count": len(rows), "classification": ReuseClass.REUSE_FOR_VALIDATION.value, "reasons": [ReasonCode.LEGACY_METRIC_ONLY.value]}


@dataclass(frozen=True)
class ReuseAudit:
    prompts: int
    answers: int
    empty_answers: int
    human_preferences: int
    human_ties: int
    invalid_human_winners: int
    duplicate_human_pairs: int
    decisions_by_judge: dict[str, int]
    legacy_decisions: int
    live_sandbox_decisions: int
    calibrated_decisions: int
    exact_historical_candidate_calls: int
    approved_final_reuse_calls: int
    frozen_planned_calls: int
    unavoidable_new_calls: int

    def serialize(self) -> dict[str, object]:
        return asdict(self)


def audit_database(session: Session, *, frozen_planned_calls: int = 16_600) -> ReuseAudit:
    prompts = session.query(Prompt).all(); answers = session.query(Answer).all(); preferences = session.query(HumanPreference).all(); decisions = session.query(JudgeDecision).all()
    categories = {prompt.id: prompt.category for prompt in prompts}
    live = [row for row in decisions if categories.get(row.prompt_id) in {"live", "live_calibrated", "ensemble_eval"}]
    calibrated = [row for row in decisions if row.judge_model_name.endswith("_calibrated")]
    pairs = {(row.prompt_id, row.answer_a_id, row.answer_b_id) for row in preferences}
    invalid = sum(row.winner_id is not None and row.winner_id not in {row.answer_a_id, row.answer_b_id} for row in preferences)
    # JudgeDecision does not hold the frozen dimensions, so no row can be an
    # exact candidate; approved reuse remains zero absent external approval.
    return ReuseAudit(len(prompts), len(answers), sum(not row.text.strip() for row in answers), len(preferences), sum(row.winner_id is None for row in preferences), invalid, len(preferences) - len(pairs), dict(sorted(Counter(row.judge_model_name for row in decisions).items())), len(decisions) - len(live), len(live), len(calibrated), 0, 0, frozen_planned_calls, frozen_planned_calls)
