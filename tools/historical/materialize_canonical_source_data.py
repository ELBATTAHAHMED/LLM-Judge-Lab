"""Materialize the committed canonical study manifest from frozen reconciliation.

This is historical/remediation tooling, not part of the normal researcher's
workflow.  It reads no database and performs no provider work.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from canonical_source_data import (  # noqa: E402
    CANONICAL_IDENTITY,
    CANONICAL_PATH,
    RAW_HUMAN_PATH,
    load_raw_source,
    sha256,
    stable_sha,
)


RECONCILIATION = ROOT / "evidence" / "final" / "controlled_source_text_corrected_v1" / "source" / "source_text_reconciliation_v1.json"


def main() -> int:
    reconciliation_bytes = RECONCILIATION.read_bytes()
    reconciliation = json.loads(reconciliation_bytes)
    source = load_raw_source()
    records = []
    for row in sorted(reconciliation["records"], key=lambda value: value["frozen_record_key"]):
        qid, turn = int(row["question_id"]), int(row["turn"])
        answers = []
        for index, model in enumerate((row["model_1"], row["model_2"])):
            answer = source.answers.get((qid, turn, model))
            if answer is None or answer.text_hash != row["corrected_source_answer_hashes"][index]:
                raise RuntimeError(f"SOURCE_TEXT_HASH_MISMATCH: {(qid, turn, model)!r}")
            answers.append({
                "model": model,
                "raw_source_identity": {"question_id": qid, "turn": turn, "model": model},
                "text_sha256": answer.text_hash,
            })
        prompt = source.prompts[(qid, turn)]
        canonical_identity = stable_sha({
            "identity": CANONICAL_IDENTITY,
            "frozen_reconciliation_identity": row["frozen_record_key"],
            "question_id": qid,
            "turn": turn,
            "answers": answers,
            "human_label": row["human_reference_label"],
        })
        records.append({
            "canonical_logical_identity": canonical_identity,
            "frozen_reconciliation_identity": row["frozen_record_key"],
            "question_id": qid,
            "turn": turn,
            "category": source.categories[qid],
            "prompt_sha256": sha256(prompt),
            "answers": answers,
            "human_preference_reference_label": row["human_reference_label"],
            "source_provenance": row["source_provenance"],
            "reconciliation_status": row["status"],
        })
    payload = {
        "identity": CANONICAL_IDENTITY,
        "description": "Canonical source-text-keyed inputs for the corrected controlled study; no database answer ordering is used.",
        "raw_source": {"path": "data/human_judgment.jsonl", "sha256": source.raw_sha256, "row_count": 3355, "dataset": "lmsys/mt_bench_human_judgments"},
        "frozen_reconciliation": {"path": "evidence/final/controlled_source_text_corrected_v1/source/source_text_reconciliation_v1.json", "sha256": sha256(reconciliation_bytes), "record_count": 1568},
        "records": records,
    }
    payload["canonical_dataset_sha256"] = stable_sha(payload)
    CANONICAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    CANONICAL_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"path": str(CANONICAL_PATH), "identity": CANONICAL_IDENTITY, "sha256": payload["canonical_dataset_sha256"], "records": len(records)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
