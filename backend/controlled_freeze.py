"""Canonical dataset freeze and human-reference independence policy."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Iterable


REVERSED_PAIR_POLICY_VERSION = "unordered-pair-consensus-v1"


@dataclass(frozen=True)
class FrozenPair:
    preference_id: int
    prompt_id: int
    answer_a_id: int
    answer_b_id: int
    answer_a_text: str
    answer_b_text: str
    answer_a_model: str
    answer_b_model: str
    category: str
    human_label: str | None

    @property
    def unordered_key(self) -> tuple[int, int, int]:
        return self.prompt_id, *sorted((self.answer_a_id, self.answer_b_id))


def canonical_dataset_checksum(pairs: Iterable[FrozenPair]) -> str:
    """Hash all immutable scientific inputs in a stable, orientation-aware form."""
    records = [asdict(pair) for pair in sorted(pairs, key=lambda p: p.preference_id)]
    material = json.dumps({"policy": REVERSED_PAIR_POLICY_VERSION, "pairs": records}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def freeze_reference_pairs(pairs: Iterable[FrozenPair]) -> tuple[list[FrozenPair], dict[str, int | str]]:
    """Collapse exact/reversed consensus records; exclude contradictory groups.

    The source has no annotator identifier, so multiple orientation records
    cannot defensibly be treated as independent observations. A unanimous
    unordered group is represented once in canonical answer-ID orientation;
    a group with distinct winners/tie outcomes is excluded rather than voted.
    """
    grouped: dict[tuple[int, int, int], list[FrozenPair]] = defaultdict(list)
    for pair in pairs:
        grouped[pair.unordered_key].append(pair)
    frozen: list[FrozenPair] = []; collapsed = conflicts = 0
    for _, group in sorted(grouped.items()):
        # Convert every label into the winner's answer ID (or tie), independent
        # of the source row's A/B orientation.
        outcomes = {None if row.human_label == "TIE" else row.answer_a_id if row.human_label == "ANSWER_A" else row.answer_b_id if row.human_label == "ANSWER_B" else "INVALID" for row in group}
        if len(outcomes) != 1:
            conflicts += 1
            continue
        representative = min(group, key=lambda row: row.preference_id)
        outcome = next(iter(outcomes))
        a, b = sorted((representative.answer_a_id, representative.answer_b_id))
        text = {representative.answer_a_id: (representative.answer_a_text, representative.answer_a_model), representative.answer_b_id: (representative.answer_b_text, representative.answer_b_model)}
        label = "TIE" if outcome is None else "ANSWER_A" if outcome == a else "ANSWER_B" if outcome == b else None
        frozen.append(FrozenPair(representative.preference_id, representative.prompt_id, a, b, text[a][0], text[b][0], text[a][1], text[b][1], representative.category, label))
        collapsed += len(group) - 1
    return frozen, {"policy": REVERSED_PAIR_POLICY_VERSION, "input_rows": sum(len(v) for v in grouped.values()), "frozen_rows": len(frozen), "collapsed_rows": collapsed, "conflicting_unordered_groups_excluded": conflicts}
