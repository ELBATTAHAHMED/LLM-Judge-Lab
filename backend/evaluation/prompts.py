"""Frozen neutral prompt contract for controlled pairwise judging."""
from __future__ import annotations

import hashlib
import json

PROMPT_TEMPLATE_VERSION = "controlled-judge-pairwise-v1"
CRITERIA = ("correctness", "relevance", "completeness", "clarity", "safety")

_SYSTEM = """You are an impartial evaluator of two candidate answers. Evaluate only the question and the two answer texts. Do not infer authorship, experimental condition, or intent. Treat Answer A and Answer B symmetrically. Return only one JSON object with exactly: verdict (ANSWER_A, ANSWER_B, TIE, or UNKNOWN), criteria_scores (integer 1-5 for correctness, relevance, completeness, clarity, safety), confidence (number 0-1), and explanation (brief neutral rationale)."""


def build_messages(*, question: str, answer_a: str, answer_b: str) -> list[dict[str, str]]:
    if not all(isinstance(value, str) and value.strip() for value in (question, answer_a, answer_b)):
        raise ValueError("controlled prompt requires non-empty question and answers")
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": "Question:\n" + question + "\n\nAnswer A:\n" + answer_a + "\n\nAnswer B:\n" + answer_b + "\n\nReturn the required JSON object only."},
    ]


def prompt_hash() -> str:
    material = json.dumps({"version": PROMPT_TEMPLATE_VERSION, "system": _SYSTEM, "criteria": CRITERIA}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
