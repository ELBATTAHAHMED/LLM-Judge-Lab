"""Provider-free publication of additive corrected current-release analyses."""
from __future__ import annotations

import json

from controlled_analysis_publisher import publish_manifest_analysis
from controlled_models import Experiment, ExperimentManifest
from database import SessionLocal
from final_evidence import CANONICAL_FINAL_MANIFESTS


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
