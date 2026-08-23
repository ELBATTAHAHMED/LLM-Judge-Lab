"""Safe CLI for the frozen multi-judge consensus execution.

Without ``--execute`` it performs only durable provider-free preflight.
"""
from __future__ import annotations

import argparse
import json

from database import SessionLocal
from multijudge_real_execution import PAID_CONFIRMATION, MultiJudgeRealRunner, format_live_progress


def _print_progress(report: dict) -> None:
    print(format_live_progress(report), flush=True)


def _print_summary(report: dict) -> None:
    print("MULTI-JUDGE EXECUTION COMPLETE", flush=True)
    print(f"Planned slots: 6444", flush=True)
    print(f"Completed: {report['completed_scientific_slots']}", flush=True)
    print(f"Terminal failures: {report['terminal_failures']}", flush=True)
    print(f"Ambiguous: {report['ambiguous']}", flush=True)
    print(f"Attempts: {report['attempts']}", flush=True)
    print(f"Retries: {report['retries']}", flush=True)
    print(f"Pending: {report['pending']}", flush=True)
    print(f"Reserved spend: ${report['cumulative_reserved_usd']}", flush=True)
    print(f"Actual spend: ${report['cumulative_actual_usd']}", flush=True)
    print("Hard cap: $2.50", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Frozen multi-judge consensus runner")
    parser.add_argument("--execute", action="store_true", help="Begin/resume paid provider execution.")
    parser.add_argument("--confirm-paid-run", help=f"Required exact acknowledgement: {PAID_CONFIRMATION}")
    args = parser.parse_args(argv)
    runner = MultiJudgeRealRunner()
    if not args.execute:
        with SessionLocal() as session:
            report = runner.preflight(session)
        print(report["state"])
        print(json.dumps(report, sort_keys=True))
        return 0 if report["state"] == "READY" else 2
    report = runner.execute(SessionLocal, confirm_paid_run=args.confirm_paid_run or "", progress_callback=_print_progress)
    _print_summary(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
