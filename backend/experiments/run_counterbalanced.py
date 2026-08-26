"""Manual-only command boundary for the counterbalanced RQ6 remediation.

``--execute`` is intentionally the sole provider-bound mode and requires both
an explicit authorization acknowledgement and the immutable manifest digest.
All other modes are provider-free.
"""
from __future__ import annotations

import argparse
import json

from backend.core.database import SessionLocal
from backend.experiments.counterbalanced import (
    EXPECTED_MANIFEST_SHA256,
    analysis_payload,
    execute_authorized,
    execution_status,
    load_preflight_manifest,
    preexecution_checks,
)


def _print(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Counterbalanced RQ6 manual execution boundary")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true", help="Read-only manifest, DB, routing, and spend-guard validation.")
    mode.add_argument("--status", action="store_true", help="Read-only RQ6-only progress and spend status.")
    mode.add_argument("--execute", action="store_true", help="Authorized provider-bound execution/resume for the new RQ6 lineage only.")
    mode.add_argument("--analyze", action="store_true", help="Read-only reconciliation and preregistered RQ6 analysis after completion.")
    parser.add_argument("--authorization-token", help="Explicit operator authorization acknowledgement; required only with --execute.")
    parser.add_argument("--confirm-manifest-sha", help="Must exactly equal the authorized counterbalanced RQ6 manifest SHA-256.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = load_preflight_manifest()
    with SessionLocal() as session:
        if args.preflight:
            _print(preexecution_checks(session, manifest))
            return 0
        if args.status:
            _print(execution_status(session, manifest))
            return 0
        if args.analyze:
            _print(analysis_payload(session, manifest))
            return 0
        if not args.authorization_token:
            raise PermissionError("--execute requires --authorization-token")
        if args.confirm_manifest_sha != EXPECTED_MANIFEST_SHA256:
            raise PermissionError("--execute requires the exact --confirm-manifest-sha value")
        _print(execute_authorized(session, manifest=manifest, authorization_token=args.authorization_token))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
