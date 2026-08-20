"""Provider-free publication command for the completed counterbalanced RQ6."""
from __future__ import annotations

import json

from database import SessionLocal
from rq6_counterbalanced_execution import load_preflight_manifest, publish_counterbalanced_analysis


def main() -> int:
    manifest = load_preflight_manifest()
    with SessionLocal() as session:
        analysis = publish_counterbalanced_analysis(session, manifest)
        session.commit()
        print(json.dumps({"analysis_run_id": str(analysis.id), "manifest_id": str(analysis.manifest_id), "design_identity": "counterbalanced-source-family-v1", "analysis_identity": "counterbalanced-source-family-analysis-v1"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
