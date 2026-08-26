"""Provider-free publication of additive corrected current-release analyses."""
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from backend.analysis.publisher import publish_manifest_analysis  # noqa: E402
from backend.core.controlled_models import Experiment, ExperimentManifest  # noqa: E402
from backend.core.database import SessionLocal  # noqa: E402
from backend.core.final_evidence import CANONICAL_FINAL_MANIFESTS  # noqa: E402


CORRECTED_RQS = ("RQ2", "RQ3", "RQ4", "RQ5", "RQ7")


def main() -> int:
    published: dict[str, str] = {}
    with SessionLocal() as session:
        for rq_code in CORRECTED_RQS:
            manifest = session.get(ExperimentManifest, CANONICAL_FINAL_MANIFESTS[rq_code])
            if manifest is None:
                raise RuntimeError(f"Missing canonical manifest for {rq_code}")
            experiment = session.get(Experiment, manifest.experiment_id)
            if experiment is None:
                raise RuntimeError(f"Missing experiment for {rq_code}")
            analysis = publish_manifest_analysis(session=session, experiment=experiment, manifest=manifest, current_release=True)
            published[rq_code] = str(analysis.id)
        session.commit()
    print(json.dumps(published, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
