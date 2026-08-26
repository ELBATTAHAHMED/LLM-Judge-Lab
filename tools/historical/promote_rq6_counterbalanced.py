"""Provider-free publication command for the completed counterbalanced RQ6."""
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from database import SessionLocal  # noqa: E402
from rq6_counterbalanced_execution import load_preflight_manifest, publish_counterbalanced_analysis  # noqa: E402


def main() -> int:
    manifest = load_preflight_manifest()
    with SessionLocal() as session:
        analysis = publish_counterbalanced_analysis(session, manifest)
        session.commit()
        print(json.dumps({"analysis_run_id": str(analysis.id), "manifest_id": str(analysis.manifest_id), "design_identity": "counterbalanced-source-family-v1", "analysis_identity": "counterbalanced-source-family-analysis-v1"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
