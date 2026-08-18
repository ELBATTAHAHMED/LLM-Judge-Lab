"""Provider-free metrics with explicit denominators and non-estimable states."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from math import isfinite
from typing import Iterable, Mapping


VALID_LABELS = frozenset({"ANSWER_A", "ANSWER_B", "TIE"})
FAILURE_LABELS = frozenset({"UNKNOWN", "INVALID_RESPONSE", "API_ERROR", "TIMEOUT"})


@dataclass(frozen=True)
class AlignmentObservation:
    human_label: str | None
    judge_label: str | None
    category: str = "uncategorized"
    judge_name: str = "unknown"


def _kappa(human: list[str], judge: list[str]) -> float | None:
    if not human:
        return None
    observed = sum(a == b for a, b in zip(human, judge)) / len(human)
    expected = sum((human.count(label) / len(human)) * (judge.count(label) / len(judge)) for label in VALID_LABELS)
    return None if expected == 1 else (observed - expected) / (1 - expected)


def rq1_alignment(observations: Iterable[AlignmentObservation]) -> dict[str, object]:
    records = list(observations)
    result = _rq1_core(records)
    valid = [r for r in records if r.human_label in VALID_LABELS and r.judge_label in VALID_LABELS]
    result["by_category"] = {category: _rq1_core(group) for category, group in _groups(valid, lambda r: r.category).items()}
    return result


def _rq1_core(records: list[AlignmentObservation]) -> dict[str, object]:
    valid = [r for r in records if r.human_label in VALID_LABELS and r.judge_label in VALID_LABELS]
    exclusions = Counter("missing_human_reference" if r.human_label not in VALID_LABELS else f"judge_{str(r.judge_label).lower()}" for r in records if r not in valid)
    human, judge = [r.human_label for r in valid], [r.judge_label for r in valid]
    return {"eligible_n": len(valid), "input_n": len(records), "exact_agreement": (sum(a == b for a, b in zip(human, judge)) / len(valid)) if valid else None, "cohens_kappa": _kappa(human, judge), "human_tie_count": human.count("TIE"), "judge_tie_count": judge.count("TIE"), "tie_agreement_count": sum(a == b == "TIE" for a, b in zip(human, judge)), "failure_or_unknown_count": sum(r.judge_label in FAILURE_LABELS for r in records), "exclusions": dict(exclusions)}


def _groups(records: Iterable[object], key):
    result = defaultdict(list)
    for record in records: result[key(record)].append(record)
    return result


@dataclass(frozen=True)
class RepetitionObservation:
    group_key: str
    prompt_id: int
    answer_a_id: int
    answer_b_id: int
    judge_name: str
    temperature: float
    repetition_index: int
    retry_count: int
    verdict: str


def rq2_consistency(observations: Iterable[RepetitionObservation]) -> dict[str, object]:
    grouped = _groups(observations, lambda r: r.group_key); summaries = []; excluded = 0
    for group in grouped.values():
        config = {(r.prompt_id, r.answer_a_id, r.answer_b_id, r.judge_name, r.temperature) for r in group}
        repetitions = {r.repetition_index for r in group}
        valid = [r.verdict for r in group if r.verdict in VALID_LABELS]
        if len(config) != 1 or len(repetitions) != len(group):
            excluded += 1; continue
        modal = max(Counter(valid).values()) if valid else 0
        summaries.append({"group_key": group[0].group_key, "n_repetitions": len(group), "valid_n": len(valid), "consistency_rate": modal / len(valid) if valid else None, "disagreement_rate": (len(valid) - modal) / len(valid) if valid else None, "failure_or_unknown_n": len(group) - len(valid), "temperature": group[0].temperature, "retry_count_total": sum(r.retry_count for r in group)})
    return {"groups": summaries, "eligible_group_n": len(summaries), "excluded_group_n": excluded, "temperature_groups": _groups(summaries, lambda r: r["temperature"])}


@dataclass(frozen=True)
class SwapObservation:
    pair_key: str
    presentation_order: str
    mapped_outcome: str
    presented_winner_slot: str | None = None


def rq3_position_sensitivity(observations: Iterable[SwapObservation]) -> dict[str, object]:
    groups = _groups(observations, lambda r: r.pair_key); counts = Counter(); slot_wins = Counter(); incomplete = 0
    for pair in groups.values():
        orders = {r.presentation_order for r in pair}
        if orders != {"AB", "BA"} or len(pair) != 2:
            incomplete += 1; continue
        a, b = sorted(pair, key=lambda r: r.presentation_order)
        for record in pair:
            if record.presented_winner_slot in {"A", "B"}: slot_wins[record.presented_winner_slot] += 1
        if a.mapped_outcome in {"ANSWER_A", "ANSWER_B"} and b.mapped_outcome in {"ANSWER_A", "ANSWER_B"}:
            counts["CONSISTENT_ORIGINAL_A" if a.mapped_outcome == b.mapped_outcome == "ANSWER_A" else "CONSISTENT_ORIGINAL_B" if a.mapped_outcome == b.mapped_outcome == "ANSWER_B" else "DECISIVE_FLIP"] += 1
        elif a.mapped_outcome == b.mapped_outcome == "TIE": counts["TIE_BOTH"] += 1
        elif "TIE" in {a.mapped_outcome, b.mapped_outcome}: counts["TIE_DISAGREEMENT"] += 1
        elif any(x in FAILURE_LABELS for x in (a.mapped_outcome, b.mapped_outcome)): counts["FAILURE_OR_UNKNOWN"] += 1
        else: counts["NONDECISIVE_DISAGREEMENT"] += 1
    paired_n = sum(counts.values()); decisive_n = counts["CONSISTENT_ORIGINAL_A"] + counts["CONSISTENT_ORIGINAL_B"] + counts["DECISIVE_FLIP"]
    return {"eligible_paired_n": paired_n, "incomplete_pair_count": incomplete, "classifications": dict(counts), "paired_decisive_flip_rate": counts["DECISIVE_FLIP"] / decisive_n if decisive_n else None, "all_paired_disagreement_rate": (counts["DECISIVE_FLIP"] + counts["TIE_DISAGREEMENT"] + counts["NONDECISIVE_DISAGREEMENT"]) / paired_n if paired_n else None, "slot_win_imbalance": (slot_wins["A"] - slot_wins["B"]) / (slot_wins["A"] + slot_wins["B"]) if sum(slot_wins.values()) else None}


def rq6_source_family_preference(records: Iterable[Mapping[str, object]]) -> dict[str, object]:
    rows = list(records); valid = [r for r in rows if r.get("winner_family") in {r.get("self_family"), r.get("other_family")}]
    slots = Counter(r.get("self_slot") for r in valid); self_wins = sum(r.get("winner_family") == r.get("self_family") for r in valid)
    balanced = abs(slots["A"] - slots["B"]) <= 1
    return {"eligible_n": len(valid), "excluded_n": len(rows) - len(valid), "self_family_preference_rate": self_wins / len(valid) if valid else None, "self_slot_counts": dict(slots), "position_balanced": balanced, "status": "ESTIMABLE" if valid and balanced else "NOT_ESTIMABLE"}


def rq7_mitigation_comparison(baseline: Mapping[str, float], mitigation: Mapping[str, float]) -> dict[str, object]:
    shared = set(baseline) & set(mitigation)
    if not shared: return {"status": "NOT_ESTIMABLE", "matched_n": 0, "changes": {}}
    changes = {key: mitigation[key] - baseline[key] for key in sorted(shared) if isfinite(mitigation[key]) and isfinite(baseline[key])}
    return {"status": "ESTIMABLE" if changes else "NOT_ESTIMABLE", "matched_n": len(shared), "changes": changes}
