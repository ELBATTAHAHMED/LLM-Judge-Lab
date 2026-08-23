"""Safe CLI for the frozen multi-judge consensus execution.

Without ``--execute`` it performs only durable provider-free preflight.
"""
from __future__ import annotations

import argparse
import json

from database import SessionLocal
from multijudge_real_execution import PAID_CONFIRMATION, MultiJudgeRealRunner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Frozen multi-judge consensus runner")
    parser.add_argument("--execute", action="store_true", help="Begin/resume paid provider execution.")
    parser.add_argument("--confirm-paid-run", help=f"Required exact acknowledgement: {PAID_CONFIRMATION}")
    args = parser.parse_args(argv)
    runner = MultiJudgeRealRunner()
    if not args.execute:
        with SessionLocal() as session:
            report = runner.preflight(session); session.commit()
        print(report["state"])
        print(json.dumps(report, sort_keys=True))
        return 0 if report["state"] == "READY" else 2
    report = runner.execute(SessionLocal, confirm_paid_run=args.confirm_paid_run or "")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
