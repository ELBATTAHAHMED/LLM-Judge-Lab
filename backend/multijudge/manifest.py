"""Provider-free materialization of the frozen multi-judge execution manifest.

This module reads the immutable research-release PostgreSQL dump only.  It does
not open a database connection, import provider clients, or create any runs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.evaluation.prompts import PROMPT_TEMPLATE_VERSION, prompt_hash
from backend.evaluation.retry_policy import FAILURE_POLICY_VERSION, RETRY_POLICY_VERSION, RETRY_RULES
from backend.core.model_registry import MODEL_REGISTRY
from backend.evaluation.routing import routing_config, routing_fingerprint, routing_policy_version
from backend.release.utils import postgres_binary


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = ROOT / "evidence" / "multijudge_consensus" / "protocol_v1.json"
MANIFEST_PATH = ROOT / "evidence" / "multijudge_consensus" / "execution_manifest_v1.json"
DUMP_PATH = ROOT / "evidence" / "final" / "research_release_v2" / "database" / "judgelab-final-research-release-v2.dump"
DATASET_IDENTITY_PATH = ROOT / "evidence" / "final" / "phase11" / "dataset" / "dataset_identity.json"
PRICING_PATH = ROOT / "backend" / "evaluation" / "pricing_config.json"
PROTOCOL_ID = "multi-judge-consensus-v1"
SEED = 20260823
JUDGES = tuple(MODEL_REGISTRY)
EXPECTED_CATEGORIES = {
    "coding": 199, "extraction": 201, "humanities": 194, "math": 193,
    "reasoning": 204, "roleplay": 217, "stem": 214, "writing": 189,
}


def _sha(value: bytes | str) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _pg_restore() -> str:
    return postgres_binary("pg_restore")


def _decode_copy(value: str) -> str | None:
    if value == r"\N":
        return None
    decoded: list[str] = []
    index = 0
    escapes = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f", "v": "\v", "\\": "\\"}
    while index < len(value):
        if value[index] != "\\":
            decoded.append(value[index]); index += 1; continue
        index += 1
        if index == len(value):
            decoded.append("\\"); break
        decoded.append(escapes.get(value[index], value[index])); index += 1
    return "".join(decoded)


def _copy_rows(table: str) -> list[list[str | None]]:
    if not DUMP_PATH.is_file():
        raise RuntimeError(f"immutable release dump is missing: {DUMP_PATH}")
    completed = subprocess.run(
        [_pg_restore(), "--data-only", f"--table={table}", "-f", "-", str(DUMP_PATH)],
        check=True, capture_output=True, encoding="utf-8", errors="strict",
    )
    lines = completed.stdout.splitlines()
    start = next((index + 1 for index, line in enumerate(lines) if line.startswith("COPY ")), None)
    if start is None:
        raise RuntimeError(f"no COPY data found for {table}")
    end = next((index for index in range(start, len(lines)) if lines[index] == r"\."), None)
    if end is None:
        raise RuntimeError(f"unterminated COPY data for {table}")
    return [[_decode_copy(field) for field in line.split("\t")] for line in lines[start:end]]


def _load_population() -> tuple[list[dict[str, Any]], dict[str, int]]:
    answers = {int(row[0]): row for row in _copy_rows("answers")}
    prompts = {int(row[0]): row for row in _copy_rows("prompts")}
    preferences = _copy_rows("human_preferences")
    groups: dict[tuple[int, int, int], list[list[str | None]]] = defaultdict(list)
    for row in preferences:
        prompt_id, answer_a_id, answer_b_id = int(row[1]), int(row[2]), int(row[3])
        groups[(prompt_id, *sorted((answer_a_id, answer_b_id)))].append(row)

    pairs: list[dict[str, Any]] = []
    conflicts = blank_answers = 0
    for (prompt_id, answer_1_id, answer_2_id), rows in sorted(groups.items()):
        winners = {None if row[4] is None else int(row[4]) for row in rows}
        if len(winners) != 1:
            conflicts += 1
            continue
        prompt, first, second = prompts.get(prompt_id), answers.get(answer_1_id), answers.get(answer_2_id)
        if prompt is None or first is None or second is None:
            raise RuntimeError("canonical reference pair has an unresolved immutable identity")
        if not all(str(value or "").strip() for value in (prompt[1], first[3], second[3])):
            blank_answers += 1
            continue
        record_material = [
            {"preference_id": int(row[0]), "prompt_id": prompt_id, "answer_a_id": int(row[2]), "answer_b_id": int(row[3]), "winner_id": None if row[4] is None else int(row[4])}
            for row in sorted(rows, key=lambda row: int(row[0]))
        ]
        pair_key = _canonical_json([prompt_id, answer_1_id, answer_2_id])
        pairs.append({
            "canonical_pair_id": _sha(f"{PROTOCOL_ID}|canonical-pair-v1|{pair_key}"),
            "canonical_pair_key": pair_key,
            "prompt_id": prompt_id,
            "original_answer_1_id": answer_1_id,
            "original_answer_2_id": answer_2_id,
            "category": str(prompt[2]),
            "prompt_sha256": _sha(str(prompt[1])),
            "original_answer_1_sha256": _sha(str(first[3])),
            "original_answer_2_sha256": _sha(str(second[3])),
            "human_reference_record_ids": [int(row[0]) for row in sorted(rows, key=lambda row: int(row[0]))],
            "human_reference_record_sha256": _sha(_canonical_json(record_material)),
        })
    summary = {
        "human_preference_records": len(preferences),
        "unordered_reference_groups": len(groups),
        "conflicting_unordered_groups_excluded": conflicts,
        "non_conflicting_canonical_pairs": len(groups) - conflicts,
        "blank_answer_pairs_excluded": blank_answers,
        "eligible_execution_pairs": len(pairs),
    }
    if summary != {
        "human_preference_records": 2396, "unordered_reference_groups": 1814,
        "conflicting_unordered_groups_excluded": 199, "non_conflicting_canonical_pairs": 1615,
        "blank_answer_pairs_excluded": 4, "eligible_execution_pairs": 1611,
    }:
        raise RuntimeError(f"unexpected canonical population reconstruction: {summary}")
    if Counter(pair["category"] for pair in pairs) != EXPECTED_CATEGORIES:
        raise RuntimeError("unexpected eligible category distribution")
    return pairs, summary


def _digest_rank(prefix: str, value: str) -> tuple[str, str]:
    return _sha(f"{PROTOCOL_ID}|{SEED}|{prefix}|{value}"), value


def _assignment(pairs: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Allocate AB exactly using the frozen category-first quota algorithm."""
    ordered_judges = tuple(sorted(JUDGES))
    quota_rank = sorted(ordered_judges, key=lambda judge: _digest_rank("quota", judge))
    global_extra_target = {judge: 3 if judge in quota_rank[:2] else 2 for judge in ordered_judges}
    odd_categories = sorted(
        (category for category, count in Counter(pair["category"] for pair in pairs).items() if count % 2),
        key=lambda category: _digest_rank("category-extra", category),
    )
    category_extras: dict[str, set[str]] = {}
    remaining = dict(global_extra_target)
    for index, category in enumerate(odd_categories):
        category_remaining = len(odd_categories) - index - 1
        choices: list[tuple[tuple[tuple[str, str], tuple[str, str]], tuple[str, str]]] = []
        for first_index, first in enumerate(ordered_judges):
            for second in ordered_judges[first_index + 1:]:
                proposed = {judge: remaining[judge] - int(judge in {first, second}) for judge in ordered_judges}
                if min(proposed.values()) < 0 or sum(proposed.values()) != 2 * category_remaining or max(proposed.values()) > category_remaining:
                    continue
                choices.append((( _digest_rank(f"category-extra|{category}", first), _digest_rank(f"category-extra|{category}", second)), (first, second)))
        if not choices:
            raise RuntimeError("no feasible category extra allocation")
        _, choice = min(choices)
        category_extras[category] = set(choice)
        for judge in choice:
            remaining[judge] -= 1
    if any(remaining.values()):
        raise RuntimeError("category extra quotas did not satisfy global balance")

    ab_by_pair: dict[str, set[str]] = {}
    for category in sorted({pair["category"] for pair in pairs}):
        rows = sorted((pair for pair in pairs if pair["category"] == category), key=lambda pair: _digest_rank("pair-order", pair["canonical_pair_key"]))
        count = len(rows)
        targets = {judge: count // 2 + int(judge in category_extras.get(category, set())) for judge in ordered_judges}
        for row_index, pair in enumerate(rows):
            remaining_rows = count - row_index - 1
            choices: list[tuple[tuple[tuple[str, str], tuple[str, str]], tuple[str, str]]] = []
            for first_index, first in enumerate(ordered_judges):
                for second in ordered_judges[first_index + 1:]:
                    proposed = {judge: targets[judge] - int(judge in {first, second}) for judge in ordered_judges}
                    if min(proposed.values()) < 0 or sum(proposed.values()) != 2 * remaining_rows or max(proposed.values()) > remaining_rows:
                        continue
                    choices.append((( _digest_rank(f"slot|{pair['canonical_pair_key']}", first), _digest_rank(f"slot|{pair['canonical_pair_key']}", second)), (first, second)))
            if not choices:
                raise RuntimeError("no feasible deterministic pair assignment")
            _, choice = min(choices)
            ab_by_pair[pair["canonical_pair_id"]] = set(choice)
            for judge in choice:
                targets[judge] -= 1
        if any(targets.values()):
            raise RuntimeError("category quota was not exhausted")
    return ab_by_pair


def _retry_metadata() -> dict[str, Any]:
    return {
        "retry_policy_version": RETRY_POLICY_VERSION,
        "failure_policy_version": FAILURE_POLICY_VERSION,
        "attempt_accounting": "Retries are operational attempts, not scientific repetitions; each pair/judge slot has at most one final scientific pass outcome.",
        "rules": {category: {"retryable": rule.retryable, "max_retries": rule.max_retries, "backoff_seconds": list(rule.backoff_seconds)} for category, rule in RETRY_RULES.items()},
    }


def build_manifest(*, created_at: str) -> dict[str, Any]:
    protocol_bytes = PROTOCOL_PATH.read_bytes()
    protocol = json.loads(protocol_bytes)
    if protocol["protocol_id"] != PROTOCOL_ID or protocol["population"]["n_planned_pairs"] != 1611 or protocol["execution_plan"]["planned_scientific_passes"] != 6444:
        raise RuntimeError("frozen protocol identity or denominators do not match Phase 3")
    pairs, exclusions = _load_population()
    if len(pairs) != protocol["population"]["n_planned_pairs"]:
        raise RuntimeError("population drift from frozen protocol")
    ab_by_pair = _assignment(pairs)
    routes, pricing = routing_config(), json.loads(PRICING_PATH.read_text(encoding="utf-8"))
    if routes["policy"]["allow_fallbacks"] is not False:
        raise RuntimeError("controlled routing must prohibit fallbacks")
    pricing_by_judge = {row["judge"]: row for row in pricing["models"]}
    judge_specs = []
    for judge in JUDGES:
        spec = MODEL_REGISTRY[judge]
        route = routes["models"].get(judge)
        if spec.provider.value == "OPENROUTER" and not route:
            raise RuntimeError(f"missing frozen OpenRouter route: {judge}")
        if judge not in pricing_by_judge:
            raise RuntimeError(f"missing frozen price: {judge}")
        judge_specs.append({
            "judge_id": judge, "provider": spec.provider.value, "requested_model": spec.requested_model,
            "provider_model_id": spec.provider_model_id, "effective_model_expectation": spec.judge_name,
            "route": "OPENAI_DIRECT" if spec.provider.value == "OPENAI" else route["upstream_provider"],
            "fallbacks_allowed": False, "max_output_tokens": spec.max_output_tokens,
            "structured_output_transport_mode": "OPENAI_JSON" if spec.provider.value == "OPENAI" else route["structured_output_transport_mode"],
        })
    planned_passes = []
    for pair in sorted(pairs, key=lambda item: item["canonical_pair_id"]):
        for judge in JUDGES:
            presentation = "AB" if judge in ab_by_pair[pair["canonical_pair_id"]] else "BA"
            displayed_a = pair["original_answer_1_id"] if presentation == "AB" else pair["original_answer_2_id"]
            displayed_b = pair["original_answer_2_id"] if presentation == "AB" else pair["original_answer_1_id"]
            immutable = f"{PROTOCOL_ID}|execution-manifest-v1|{_sha(protocol_bytes)}|{pair['canonical_pair_id']}|{judge}|{presentation}"
            planned_passes.append({
                "planned_pass_id": _sha(f"planned-pass|{immutable}"), "idempotency_key": _sha(f"idempotency|{immutable}"),
                "canonical_pair_id": pair["canonical_pair_id"], "judge_id": judge, "presentation": presentation,
                "original_answer_1_id": pair["original_answer_1_id"], "original_answer_2_id": pair["original_answer_2_id"],
                "displayed_A_answer_id": displayed_a, "displayed_B_answer_id": displayed_b,
            })
    dataset_identity = json.loads(DATASET_IDENTITY_PATH.read_text(encoding="utf-8"))
    manifest = {
        "manifest_id": "multi-judge-consensus-execution-manifest-v1", "manifest_version": 1, "created_at": created_at,
        "execution_authorized": False, "protocol_id": PROTOCOL_ID, "protocol_sha256": _sha(protocol_bytes),
        "dataset": {"dataset_version_id": dataset_identity["dataset_version_id"], "dataset_source": dataset_identity["dataset_source"], "dataset_sha256": dataset_identity["dataset_sha256"], "source_release_dump_sha256": _sha(DUMP_PATH.read_bytes()), "reference_policy": "unordered-pair-consensus-v1"},
        "population": {"n_planned_pairs": len(pairs), "exclusions": exclusions, "category_distribution": dict(sorted(Counter(pair["category"] for pair in pairs).items())), "human_reference_outcome_in_manifest": False},
        "scientific_configuration": {
            "seed": SEED, "presentation_algorithm_version": "category-balanced-quota-v1", "judges": judge_specs,
            "prompt": {"template_version": PROMPT_TEMPLATE_VERSION, "template_sha256": prompt_hash(), "temperature": 0, "top_p": 1, "response_schema": {"verdict": ["ANSWER_A", "ANSWER_B", "TIE", "UNKNOWN"], "criteria_scores": "integer 1-5 for correctness,relevance,completeness,clarity,safety", "confidence": "number 0-1", "explanation": "brief neutral rationale"}, "parser_contract": "controlled_evaluation.NormalizedEvaluationResult"},
            "routing_policy_version": routing_policy_version(), "routing_fingerprint": routing_fingerprint(), "retry_policy": _retry_metadata(),
        },
        "pairs": sorted(pairs, key=lambda item: item["canonical_pair_id"]),
        "planned_passes": planned_passes,
        "accounting": {"planned_pairs": 1611, "planned_scientific_passes": len(planned_passes), "calls_per_judge": {judge: sum(item["judge_id"] == judge for item in planned_passes) for judge in JUDGES}, "openai_direct_calls": sum(item["judge_id"] == "gpt-4o-mini" for item in planned_passes), "openrouter_calls": sum(item["judge_id"] != "gpt-4o-mini" for item in planned_passes), "global_presentations": {"AB": sum(item["presentation"] == "AB" for item in planned_passes), "BA": sum(item["presentation"] == "BA" for item in planned_passes)}, "per_judge_presentations": {judge: {presentation: sum(item["judge_id"] == judge and item["presentation"] == presentation for item in planned_passes) for presentation in ("AB", "BA")} for judge in JUDGES}},
        "budget_metadata": {"hard_cap_usd": "2.50", "expected_usd": "1.3736", "p90_usd": "1.9338", "p90_plus_15pct_retries_usd": "2.2239", "pricing_version": pricing["version"], "estimates_are_scientific_results": False},
        "evidence_class_safety": {"source_evidence": "canonical human-reference lineage only", "excluded_inputs": ["PILOT", "SUPERSEDED", "legacy exploratory decisions", "Live Evaluation", "qualitative CSV judgments", "manually edited judgments"], "additive_to_phase11": True},
    }
    validate_manifest(manifest)
    return manifest


def validate_manifest(manifest: dict[str, Any]) -> None:
    pairs, passes = manifest["pairs"], manifest["planned_passes"]
    if len(pairs) != 1611 or len({pair["canonical_pair_id"] for pair in pairs}) != 1611:
        raise RuntimeError("invalid canonical-pair count or identity uniqueness")
    if len({pair["canonical_pair_key"] for pair in pairs}) != 1611 or any(pair["original_answer_1_id"] >= pair["original_answer_2_id"] for pair in pairs):
        raise RuntimeError("invalid unordered original-answer identity")
    if len(passes) != 6444 or len({row["planned_pass_id"] for row in passes}) != 6444 or len({row["idempotency_key"] for row in passes}) != 6444:
        raise RuntimeError("invalid pass or idempotency count")
    by_pair: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in passes:
        by_pair[row["canonical_pair_id"]].append(row)
        expected = (row["original_answer_1_id"], row["original_answer_2_id"]) if row["presentation"] == "AB" else (row["original_answer_2_id"], row["original_answer_1_id"])
        if (row["displayed_A_answer_id"], row["displayed_B_answer_id"]) != expected:
            raise RuntimeError("displayed answer mapping drift")
    if any(len(rows) != 4 or {row["judge_id"] for row in rows} != set(JUDGES) or Counter(row["presentation"] for row in rows) != {"AB": 2, "BA": 2} for rows in by_pair.values()):
        raise RuntimeError("invalid per-pair four-judge presentation schedule")
    accounting = manifest["accounting"]
    if accounting["global_presentations"] != {"AB": 3222, "BA": 3222} or any(sorted(counts.values()) != [805, 806] for counts in accounting["per_judge_presentations"].values()):
        raise RuntimeError("invalid global/per-judge counterbalance")
    if manifest["execution_authorized"] is not False or manifest["population"]["human_reference_outcome_in_manifest"] is not False:
        raise RuntimeError("execution authorization or human-reference leakage violation")


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize the provider-free frozen multi-judge execution manifest.")
    parser.add_argument("--created-at", default=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    parser.add_argument("--output", type=Path, default=MANIFEST_PATH)
    args = parser.parse_args()
    manifest = build_manifest(created_at=args.created_at)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"WROTE {args.output}")
    print(f"SHA256 {_sha(args.output.read_bytes())}")


if __name__ == "__main__":
    main()
