"""Provider-free planning entry point for a canonical controlled evaluation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.core.database import SessionLocal  # noqa: E402
from backend.evaluation.planning import call_plan, database_pairs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan canonical controlled evaluation; this command never contacts a provider.")
    parser.add_argument("--limit", type=int, default=80, help="Maximum selected base units per RQ/judge.")
    args = parser.parse_args()
    with SessionLocal() as session:
        # `build_dataset.py` has already applied the frozen source-correct
        # consensus.  Re-freezing against historical duplicates would make a
        # fresh plan depend on data that is not part of the canonical build.
        pairs = database_pairs(session, apply_reference_policy=False)
    plan = call_plan(pairs, limit=args.limit, snapshot_id="source-corrected-controlled-study-v1")
    print(json.dumps({"provider_calls": 0, "pair_records": len(pairs), "plan": plan}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
