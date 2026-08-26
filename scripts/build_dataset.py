"""Build the canonical source-correct controlled dataset into an empty database."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.data.canonical import build_fresh_dataset  # noqa: E402
from backend.core.database import SessionLocal  # noqa: E402


def main() -> int:
    argparse.ArgumentParser(description="Build canonical source-correct data into an empty database.").parse_args()
    with SessionLocal.begin() as session:
        report = build_fresh_dataset(session)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
