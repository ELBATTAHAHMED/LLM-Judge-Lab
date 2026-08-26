"""Explicitly finalize status metadata for the seven frozen controlled RQs.

This is intentionally not invoked by web-app startup.  It changes only the
``status`` columns of canonical experiments and manifests after validating
their immutable AnalysisRun lineage.  The database's manifest-status
constraint defines ``FROZEN`` as the compatible final state.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from controlled_models import AnalysisRun, Experiment, ExperimentManifest  # noqa: E402
from database import SessionLocal  # noqa: E402
from final_evidence import canonical_final_analysis_runs  # noqa: E402


def final_metadata_rows(session):
    rows = session.query(AnalysisRun).all()
    canonical, error = canonical_final_analysis_runs(rows)
    if canonical is None:
        raise RuntimeError(error or "Canonical final evidence is unavailable.")
    return [canonical[rq] for rq in sorted(canonical)]


def apply_final_metadata(session) -> list[tuple[str, str, str]]:
    """Set canonical experiments to ``COMPLETED`` and manifests to ``FROZEN``."""
    changed: list[tuple[str, str, str]] = []
    for analysis in final_metadata_rows(session):
        experiment = session.get(Experiment, analysis.experiment_id)
        manifest = session.get(ExperimentManifest, analysis.manifest_id)
        if experiment is None or manifest is None:
            raise RuntimeError(f"Missing canonical experiment/manifest for {analysis.rq_code}.")
        if manifest.experiment_id != experiment.id:
            raise RuntimeError(f"Broken canonical experiment/manifest linkage for {analysis.rq_code}.")
        experiment.status = "COMPLETED"
        manifest.status = "FROZEN"
        changed.append((analysis.rq_code, str(experiment.id), str(manifest.id)))
    session.flush()
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="commit the validated status-only metadata update")
    args = parser.parse_args()
    session = SessionLocal()
    try:
        rows = final_metadata_rows(session)
        if not args.apply:
            for row in rows:
                print(f"{row.rq_code}: experiment {row.experiment_id} -> COMPLETED; manifest {row.manifest_id} -> FROZEN")
            print("Dry run only. Re-run with --apply to update status metadata.")
            return 0
        changed = apply_final_metadata(session)
        session.commit()
        for rq_code, experiment_id, manifest_id in changed:
            print(f"{rq_code}: experiment {experiment_id} -> COMPLETED; manifest {manifest_id} -> FROZEN")
        return 0
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
