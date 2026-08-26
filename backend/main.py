import sys
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal
import os

import math
import re
import pandas as pd
from pydantic import BaseModel, Field
from scipy.stats import chisquare
from sklearn.metrics import cohen_kappa_score
import uuid
import json
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.orm import Session

# ── Path & sys.path setup ─────────────────────────────────────────────────────
# backend/main.py lives inside backend/
BACKEND_DIR = Path(__file__).parent.resolve()
ROOT_DIR    = BACKEND_DIR.parent.resolve()

# Resolve the local configuration from the repository root so the manual-only
# sandbox setting survives local restarts regardless of the Uvicorn cwd.
load_dotenv(ROOT_DIR / ".env")

# Ensure backend/ directory is in sys.path so 'database' and 'models' import cleanly
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Import engine and Base for table creation, and get_db dependency
from backend.core.database import engine, Base, get_db, resync_postgres_sequences  # noqa: E402
import backend.core.models  # noqa: E402
from backend.core.controlled_models import AnalysisRun, ControlledRun, ExperimentManifest, ExperimentalUnit, RunPass  # noqa: E402
from backend.evaluation.persistence import EvidenceClass  # noqa: E402
from backend.core.final_evidence import (  # noqa: E402
    CANONICAL_FINAL_ANALYSIS_RUNS,
    CANONICAL_FINAL_MANIFESTS,
    CANONICAL_RQ7_SECONDARY_ANALYSIS_RUN,
    CORRECTED_ARTIFACT_SHA256,
    CORRECTED_ANALYSIS_VERSION,
    canonical_final_analysis_runs,
)
from backend.analysis.consistency import compute_inter_judge_kappa, _adjust_pvalues_bh  # noqa: E402
from backend.evaluation.live import call_judge, call_calibrated_judge, call_multi_judge_ensemble, is_local_model  # noqa: E402


logger = logging.getLogger(__name__)

QUALITATIVE_DIR      = ROOT_DIR / "qualitative_data"

# Valid bucket names → CSV filename mapping
BUCKET_FILES: dict[str, str] = {
    "verbosity":          "qualitative_verbosity.csv",
    "forced_choice":      "qualitative_forced_choice.csv",
    "position_bias":      "qualitative_position_bias.csv",
    "baseline_alignment": "qualitative_baseline_alignment.csv",
}


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI application.

    Normal final startup is read-only.  Explicit local maintenance remains
    available behind an opt-in environment flag.
    """
    if os.getenv("JUDGELAB_RUN_MAINTENANCE_ON_STARTUP", "false").lower() == "true":
        try:
            Base.metadata.create_all(bind=engine)
            resync_postgres_sequences(engine)
        except Exception as e:
            print(f"Warning: explicit startup maintenance skipped ({e})")
    yield


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="LLM-as-a-Judge Reliability Lab API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configurations to allow local frontend communication
_cors_origins = [origin.strip() for origin in os.getenv("JUDGELAB_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _live_sandbox_provider_calls_enabled() -> bool:
    return os.getenv("ENABLE_LIVE_SANDBOX_PROVIDER_CALLS", "false").strip().lower() == "true"


def _require_live_sandbox_enabled() -> None:
    """Disabled-by-default boundary before any manual provider transport."""
    if not _live_sandbox_provider_calls_enabled():
        raise HTTPException(status_code=403, detail="Live sandbox provider calls are disabled before provider transport.")


@app.get("/api/live-sandbox/status")
def get_live_sandbox_status() -> dict[str, bool]:
    """Expose only the local manual-execution opt-in state; never provider credentials."""
    return {"enabled": _live_sandbox_provider_calls_enabled()}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sanitize(value: Any) -> Any:
    """Replace NaN / Inf float values with None so JSON serialization is safe."""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame to a list of dicts, sanitizing non-JSON floats."""
    records = df.to_dict(orient="records")
    return [
        {k: _sanitize(v) for k, v in row.items()}
        for row in records
    ]


def _classify_format_text(text_content: str) -> str:
    """Classify response text as 'markdown_heavy' or 'plain_text'."""
    if not text_content:
        return "plain_text"
    score = 0
    if re.search(r'(?m)^#{1,6}\s', text_content):
        score += 1
    if re.search(r'\*\*.*?\*\*', text_content):
        score += 1
    if re.search(r'(?m)^\s*[*\-]\s', text_content):
        score += 1
    if re.search(r'(?m)^\s*\d+\.\s', text_content):
        score += 1
    if re.search(r'```', text_content):
        score += 2
    return "markdown_heavy" if score >= 2 else "plain_text"

# ── Pydantic Response Schemas ──────────────────────────────────────────────────

class HealthCheckResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    database: str
    message: str


class LeaderboardItem(BaseModel):
    model: str
    raw_win_rate: float
    bt_score: float
    quality_tier: str
    neutralized_score: float


class BiasStatsResponse(BaseModel):
    evidence_class: Literal["LEGACY_EXPLORATORY"]
    status: Literal["AVAILABLE", "NO_DATA"]
    n: int
    verbosity_data: list[dict[str, Any]]
    position_data: dict[str, int | None]
    domain_kappa: list[dict[str, Any]]
    format_bias: dict[str, Any]
    inter_judge_kappa: float | None = None


class EvaluateResponse(BaseModel):
    winner: str
    verbatim_reasoning: str
    model_name: str


class CalibratedEvaluationResponse(BaseModel):
    status: str
    original_order_winner: str
    swapped_order_winner: str
    position_bias_detected: bool
    final_calibrated_winner: str
    detailed_reasoning: Any = None
    total_input_tokens: int | None = None
    total_output_tokens: int | None = None
    model_name: str


class DatasetCountResponse(BaseModel):
    status: Literal["AVAILABLE", "NO_DATA", "UNAVAILABLE"]
    count: int | None
    message: str


class InterJudgeKappaResponse(BaseModel):
    evidence_class: Literal["LEGACY_EXPLORATORY"]
    status: Literal["AVAILABLE", "NO_DATA"]
    n: int
    inter_judge_kappa: float | None
    overlapping_trials: int
    agreement_rate: float | None
    model_a: str
    model_b: str


class SelfPreferenceResponse(BaseModel):
    evidence_class: Literal["LEGACY_EXPLORATORY"]
    status: Literal["AVAILABLE", "NO_DATA"]
    n: int
    judge_model: str
    judge_family: str
    self_win_rate: float | None = None
    baseline_win_rate: float | None = None
    self_preference_ratio: float | None = None
    self_preference_detected: bool
    total_self_matchups: int
    total_other_matchups: int
    p_value: float | None = None
    statistically_significant: bool


class ControlledResultsAccounting(BaseModel):
    """Final-science accounting derived only from CONTROLLED run evidence."""
    planned_units: int
    succeeded_units: int
    valid_partial_units: int
    failed_units: int
    pending_units: int
    planned_pass_slots: int
    valid_returned_passes: int
    failed_pass_slots: int
    provider_error_pass_slots: int = 0
    invalid_response_pass_slots: int = 0
    paired_excluded_valid_pass_slots: int = 0


class ControlledResultsResponse(BaseModel):
    """Controlled-only endpoint; never falls back to legacy or mock evidence."""
    status: str
    evidence_class: Literal["CONTROLLED"]
    executed_runs: int
    executed_passes: int
    accounting: ControlledResultsAccounting | None = None
    analysis_runs: dict[str, str] = {}
    secondary_mitigations: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []
    message: str


def serialize_multi_judge_secondary(rows: list[AnalysisRun]) -> tuple[dict[str, dict[str, Any]] | None, str | None]:
    """Fail closed: a promoted secondary result has one complete DB record."""
    if len(rows) != 1:
        return None, "Promoted secondary mitigation analysis is unavailable or ambiguous."
    run = rows[0]
    payload = run.result_json or {}
    metrics = payload.get("metrics") if (
        run.rq_code == "RQ7"
        and run.analysis_version == CORRECTED_ANALYSIS_VERSION
        and payload.get("rq_key") == "RQ7_SECONDARY"
    ) else None
    required = {
        "planned_n", "consensus_covered_n", "agreement", "coverage",
        "equal_weight_individual_comparator", "matched_delta", "matched_delta_ci_95",
    }
    ci = metrics.get("matched_delta_ci_95") if isinstance(metrics, dict) else None
    if (
        not isinstance(metrics, dict)
        or not required.issubset(metrics)
        or not isinstance(ci, dict)
        or not all(isinstance(ci.get(key), (int, float)) for key in ("low", "high"))
        or payload.get("analysis_artifact_identity") != CORRECTED_ANALYSIS_VERSION
        or payload.get("artifact_sha256") != CORRECTED_ARTIFACT_SHA256
    ):
        return None, "Promoted secondary mitigation analysis has an invalid provenance contract."
    return {"multi_judge_consensus": {"analysis_run_id": str(run.id), "role": "SECONDARY", "method_family": "cross_judge_aggregation", "planned_n": metrics["planned_n"], "retained_n": metrics["consensus_covered_n"], "agreement": metrics["agreement"], "coverage": metrics["coverage"], "comparator": "equal_weight_individual_judge_baseline_same_retained_pairs", "comparator_agreement": metrics["equal_weight_individual_comparator"], "matched_delta": metrics["matched_delta"], "ci_95": {"low": ci["low"], "high": ci["high"]}, "protocol_id": payload["analysis_artifact_identity"], "package_id": payload["artifact_sha256"], "direct_dualswap_comparison": "NOT_DEFENSIBLE", "comparison_reason": "different frozen units and estimands", "coverage_unit": "canonical_answer_pairs"}}, None


def serialize_corrected_metric_rows(published_by_rq: dict[str, AnalysisRun]) -> tuple[list[dict[str, Any]] | None, str | None]:
    """Adapt canonical AnalysisRun metric maps to the public metric contract.

    The controller never contains scientific values: it only exposes the
    already-pinned metrics from the authoritative source-corrected AnalysisRuns.
    """
    rows: list[dict[str, Any]] = []
    required = {
        "metric_name", "value", "numerator", "denominator", "eligible_n",
        "analyzed_n", "tie_count", "unknown_count", "failure_count",
        "excluded_count", "ci_low", "ci_high", "status", "metric_version",
    }
    for rq, run in sorted(published_by_rq.items()):
        metrics = (run.result_json or {}).get("metrics")
        if not isinstance(metrics, dict):
            return None, "Published controlled analysis has an invalid metric contract."
        for metric_key, serialized in metrics.items():
            if not isinstance(serialized, dict) or not required.issubset(serialized):
                return None, "Published controlled analysis has an invalid metric contract."
            judge = serialized.get("judge")
            if metric_key.startswith("judge:"):
                _, judge, _ = metric_key.split(":", 2)
            row = {
                "rq": rq,
                "metric_key": metric_key,
                "judge": judge,
                "condition": serialized.get("condition"),
                "metric": serialized["metric_name"],
                "value": serialized["value"],
                "numerator": serialized["numerator"],
                "denominator": serialized["denominator"],
                "eligible_n": serialized["eligible_n"],
                "analyzed_n": serialized["analyzed_n"],
                "ties": serialized["tie_count"],
                "unknowns": serialized["unknown_count"],
                "failures": serialized["failure_count"],
                "excluded": serialized["excluded_count"],
                "ci_low": serialized["ci_low"],
                "ci_high": serialized["ci_high"],
                "status": serialized["status"],
                "analysis_version": serialized["metric_version"],
                "evidence_class": EvidenceClass.CONTROLLED.value,
            }
            if metric_key.startswith("baseline_"):
                row["condition"] = "BASELINE SINGLE-PASS"
            elif metric_key.startswith("dual_swap_"):
                row["condition"] = "DUAL_SWAP"
            elif metric_key.endswith("_delta"):
                row["condition"] = "DUAL_SWAP − BASELINE SINGLE-PASS"
            rows.append(row)
    return rows or None, None if rows else "Published controlled analysis has no metrics."


# ── GET / & GET /health (Health Check) ───────────────────────────────────────

@app.get("/", response_model=HealthCheckResponse)
@app.get("/health", response_model=HealthCheckResponse)
def health_check(db: Session = Depends(get_db)) -> HealthCheckResponse:
    """Report dependency health without exposing connection details."""
    try:
        db.execute(text("SELECT 1"))
        return HealthCheckResponse(
            status="healthy",
            database="connected",
            message="LLM-as-a-Judge Reliability Lab Backend is running.",
        )
    except Exception:
        return HealthCheckResponse(
            status="unhealthy",
            database="unavailable",
            message="Database connectivity is unavailable.",
        )


@app.get("/api/controlled/results", response_model=ControlledResultsResponse)
def controlled_results(db: Session = Depends(get_db)) -> ControlledResultsResponse:
    """Expose final controlled evidence only after a real controlled analysis exists."""
    # Accounting needs only these identifiers/status fields.  Selecting ORM
    # entities here would also deserialize stored provider responses and other
    # provenance blobs for every controlled run.
    controlled_runs = db.query(
        ControlledRun.id,
        ControlledRun.experimental_unit_id,
        ControlledRun.status,
    ).filter(
        ControlledRun.metadata_json["evidence_class"].as_string() == EvidenceClass.CONTROLLED.value
    ).all()
    run_ids = [run.id for run in controlled_runs]
    controlled_passes = db.query(RunPass.run_id, RunPass.outcome).filter(RunPass.run_id.in_(run_ids)).all() if run_ids else []
    if not controlled_runs or not controlled_passes:
        return ControlledResultsResponse(status="NO_CONTROLLED_EVIDENCE", evidence_class="CONTROLLED", executed_runs=len(controlled_runs), executed_passes=len(controlled_passes), results=[], message="Controlled experiment is planned but has not yet been executed.")

    passes_by_run: dict[Any, list[RunPass]] = {}
    for pass_ in controlled_passes:
        passes_by_run.setdefault(pass_.run_id, []).append(pass_)
    valid_outcomes = {"ANSWER_A", "ANSWER_B", "TIE", "UNKNOWN"}
    valid_partial_ids = {
        run.id for run in controlled_runs
        if run.status == "PARTIAL" and len(passes_by_run.get(run.id, [])) == 2
        and all(pass_.outcome in valid_outcomes for pass_ in passes_by_run[run.id])
    }
    succeeded = [run for run in controlled_runs if run.status == "SUCCEEDED"]
    failed = [run for run in controlled_runs if run.status == "FAILED" or (run.status == "PARTIAL" and run.id not in valid_partial_ids)]
    terminal_ids = {run.id for run in succeeded} | valid_partial_ids | {run.id for run in failed}

    units = {
        unit.id: unit for unit in db.query(
        ExperimentalUnit.id,
        ExperimentalUnit.manifest_id,
        ExperimentalUnit.condition_code,
        ExperimentalUnit.presentation_order,
        ).filter(
            ExperimentalUnit.id.in_([run.experimental_unit_id for run in controlled_runs])
        ).all()
    }
    manifests = {
        manifest.id: manifest for manifest in db.query(
            ExperimentManifest.id,
            ExperimentManifest.rq_code,
        ).filter(
            ExperimentManifest.id.in_([unit.manifest_id for unit in units.values()])
        ).all()
    }
    def planned_slots(run: ControlledRun) -> int:
        unit = units[run.experimental_unit_id]
        rq_code = manifests[unit.manifest_id].rq_code
        return 2 if rq_code in {"RQ3", "RQ4", "RQ5"} or unit.condition_code == "DUAL_SWAP" or unit.presentation_order == "AB_BA" else 1

    # Phase 11's frozen accounting treats a pass from a terminally incomplete
    # paired run as excluded even when that individual pass has a parsable
    # outcome.  The repaired RQ6 protocol reports its actual valid pass
    # outcomes directly, as required by its counterbalanced analysis contract.
    counterbalanced_rq6_manifest_id = uuid.UUID(CANONICAL_FINAL_MANIFESTS["RQ6"])
    counterbalanced_runs = [run for run in controlled_runs if units[run.experimental_unit_id].manifest_id == counterbalanced_rq6_manifest_id]
    counterbalanced_run_ids = {run.id for run in counterbalanced_runs}
    historical_runs = [run for run in controlled_runs if run.id not in counterbalanced_run_ids]
    historical_valid_runs = [*[
        run for run in historical_runs if run.status == "SUCCEEDED"
    ], *[
        run for run in historical_runs if run.id in valid_partial_ids
    ]]
    planned_pass_slots = sum(planned_slots(run) for run in controlled_runs)
    historical_valid_run_ids = {run.id for run in historical_valid_runs}
    valid_returned_passes = (
        sum(planned_slots(run) for run in historical_valid_runs)
        + sum(pass_.outcome in valid_outcomes for pass_ in controlled_passes if pass_.run_id in counterbalanced_run_ids)
    )
    provider_error_pass_slots = sum(pass_.outcome == "API_ERROR" for pass_ in controlled_passes)
    invalid_response_pass_slots = sum(pass_.outcome == "INVALID_RESPONSE" for pass_ in controlled_passes)
    paired_excluded_valid_pass_slots = sum(
        pass_.outcome in valid_outcomes
        for pass_ in controlled_passes
        if pass_.run_id not in counterbalanced_run_ids and pass_.run_id not in historical_valid_run_ids
    )
    nonvalid_or_excluded_slots = planned_pass_slots - valid_returned_passes
    if nonvalid_or_excluded_slots != provider_error_pass_slots + invalid_response_pass_slots + paired_excluded_valid_pass_slots:
        return ControlledResultsResponse(status="CONTROLLED_RESULTS_PENDING_ANALYSIS", evidence_class="CONTROLLED", executed_runs=len(controlled_runs), executed_passes=len(controlled_passes), results=[], message="Controlled pass accounting has an unclassified non-valid slot.")
    accounting = ControlledResultsAccounting(
        planned_units=len(controlled_runs),
        succeeded_units=len(succeeded),
        valid_partial_units=len(valid_partial_ids),
        failed_units=len(failed),
        pending_units=len(controlled_runs) - len(terminal_ids),
        planned_pass_slots=planned_pass_slots,
        valid_returned_passes=valid_returned_passes,
        failed_pass_slots=nonvalid_or_excluded_slots,
        provider_error_pass_slots=provider_error_pass_slots,
        invalid_response_pass_slots=invalid_response_pass_slots,
        paired_excluded_valid_pass_slots=paired_excluded_valid_pass_slots,
    )
    canonical_rows = db.query(AnalysisRun).filter(
        AnalysisRun.id.in_([uuid.UUID(run_id) for run_id in CANONICAL_FINAL_ANALYSIS_RUNS.values()])
    ).all()
    published_by_rq, canonical_error = canonical_final_analysis_runs(canonical_rows)
    if published_by_rq is None:
        return ControlledResultsResponse(status="CONTROLLED_RESULTS_PENDING_ANALYSIS", evidence_class="CONTROLLED", executed_runs=len(controlled_runs), executed_passes=len(controlled_passes), accounting=accounting, results=[], message=canonical_error or "Canonical final controlled analysis is unavailable.")
    secondary_runs = db.query(AnalysisRun).filter(AnalysisRun.id == uuid.UUID(CANONICAL_RQ7_SECONDARY_ANALYSIS_RUN)).all()
    if len(secondary_runs) != 1:
        return ControlledResultsResponse(status="CONTROLLED_RESULTS_PENDING_ANALYSIS", evidence_class="CONTROLLED", executed_runs=len(controlled_runs), executed_passes=len(controlled_passes), accounting=accounting, results=[], message="Promoted secondary mitigation analysis is unavailable or ambiguous.")
    secondary_mitigations, secondary_error = serialize_multi_judge_secondary(secondary_runs)
    if secondary_mitigations is None:
        return ControlledResultsResponse(status="CONTROLLED_RESULTS_PENDING_ANALYSIS", evidence_class="CONTROLLED", executed_runs=len(controlled_runs), executed_passes=len(controlled_passes), accounting=accounting, results=[], message=secondary_error or "Promoted secondary mitigation analysis is invalid.")
    rows, rows_error = serialize_corrected_metric_rows(published_by_rq)
    if rows is None:
        return ControlledResultsResponse(status="CONTROLLED_RESULTS_PENDING_ANALYSIS", evidence_class="CONTROLLED", executed_runs=len(controlled_runs), executed_passes=len(controlled_passes), accounting=accounting, results=[], message="Published controlled analysis has an invalid result contract.")
    return ControlledResultsResponse(
        status="CONTROLLED_RESULTS_AVAILABLE",
        evidence_class="CONTROLLED",
        executed_runs=len(controlled_runs),
        executed_passes=len(controlled_passes),
        accounting=accounting,
        analysis_runs={rq: str(run.id) for rq, run in sorted(published_by_rq.items())},
        secondary_mitigations=secondary_mitigations,
        results=rows,
        message="Authoritative source-corrected full-population analysis selected by pinned AnalysisRun identity; Phase 11 remains immutable historical provenance.",
    )


# ── Model ID Normalization Utility ────────────────────────────────────────────

def normalize_model_id(raw_id: str | None) -> str:
    """
    Standardize LLM Model IDs across backend endpoints to ensure seamless matching
    between UI input strings, OpenRouter identifiers, database records, and CSV artifacts.
    Strips provider prefixes when necessary and maps legacy/alias strings.
    """
    if not raw_id:
        return "gpt-4o-mini"

    val = raw_id.strip()

    canonical_map = {
        "gpt-4": "gpt-4o-mini",
        "gpt4": "gpt-4o-mini",
        "gpt-4o": "gpt-4o-mini",
        "gpt-4o-mini": "gpt-4o-mini",
        "deepseek": "deepseek/deepseek-chat",
        "deepseek-chat": "deepseek/deepseek-chat",
        "deepseek/deepseek-chat": "deepseek/deepseek-chat",
        "llama3": "meta-llama/llama-3.3-70b-instruct",
        "llama-13b": "meta-llama/llama-3.3-70b-instruct",
        "llama-3.3-70b": "meta-llama/llama-3.3-70b-instruct",
        "llama-3.3-70b-instruct": "meta-llama/llama-3.3-70b-instruct",
        "meta-llama/llama-3.3-70b-instruct": "meta-llama/llama-3.3-70b-instruct",
        "claude": "anthropic/claude-3-haiku",
        "claude-3-haiku": "anthropic/claude-3-haiku",
        "claude-3.5-haiku": "anthropic/claude-3-haiku",
        "anthropic/claude-3-haiku": "anthropic/claude-3-haiku",
    }

    if val in canonical_map:
        return canonical_map[val]

    unprefixed = val.split("/")[-1] if "/" in val else val
    if unprefixed in canonical_map:
        return canonical_map[unprefixed]

    return val


# ── GET /api/stats/self-preference ───────────────────────────────────────────

@app.get("/api/stats/self-preference", response_model=SelfPreferenceResponse)
def get_self_preference(
    judge_model: str = "gpt-4o-mini",
    db: Session = Depends(get_db),
) -> dict:
    """
    Calculate Self-Preference Bias for a judge model, measuring whether it systematically favors its own model family.
    """
    judge_model_norm = normalize_model_id(judge_model)
    try:
        from backend.analysis.consistency import compute_self_preference_bias
        payload = compute_self_preference_bias(db, judge_model_name=judge_model_norm)
        payload["evidence_class"] = "LEGACY_EXPLORATORY"
        payload["n"] = int(payload.get("total_self_matchups") or 0)
        payload["status"] = "AVAILABLE" if payload["n"] else "NO_DATA"
        return payload
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Exploratory source-family telemetry is unavailable.",
        )


# ── GET /api/stats/inter-judge-kappa ─────────────────────────────────────────

@app.get("/api/stats/inter-judge-kappa", response_model=InterJudgeKappaResponse)
def get_inter_judge_kappa(
    model_a: str = "gpt-4o-mini",
    model_b: str = "deepseek/deepseek-chat",
    db: Session = Depends(get_db),
) -> dict:
    """
    Calculate Inter-Judge Cohen's Kappa score comparing model_a vs model_b decisions.
    """
    model_a_norm = normalize_model_id(model_a)
    model_b_norm = normalize_model_id(model_b)
    try:
        from backend.analysis.consistency import compute_inter_judge_kappa
        payload = compute_inter_judge_kappa(db.get_bind(), model_a=model_a_norm, model_b=model_b_norm)
        n = int(payload.get("overlapping_trials") or 0)
        payload["evidence_class"] = "LEGACY_EXPLORATORY"
        payload["status"] = "AVAILABLE" if n else "NO_DATA"
        payload["n"] = n
        if not n:
            payload["inter_judge_kappa"] = None
            payload["agreement_rate"] = None
        return payload
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Exploratory inter-judge telemetry is unavailable.",
        )



# ── GET /api/stats/dataset-count ─────────────────────────────────────────────

@app.get("/api/stats/dataset-count", response_model=DatasetCountResponse)
def get_dataset_count(db: Session = Depends(get_db)) -> DatasetCountResponse:
    """Return the exact count of human_preferences records in the database."""
    try:
        count_val = db.execute(text("SELECT COUNT(*) FROM human_preferences")).scalar() or 0
        count = int(count_val)
        return DatasetCountResponse(
            status="AVAILABLE" if count else "NO_DATA",
            count=count,
            message="Total human preference pairwise comparisons in benchmark database." if count else "No human preference comparisons are available.",
        )
    except Exception:
        return DatasetCountResponse(
            status="UNAVAILABLE",
            count=None,
            message="Dataset count is unavailable because the database could not be queried.",
        )


def compute_leaderboard_read_only(db_engine, judge_model: str) -> list[dict]:
    """Build historical leaderboard telemetry in memory when its cache is absent.

    The public endpoint must remain read-only: this deliberately does not
    recreate the retired CSV artifacts or alter the database.  It preserves the
    historical/exploratory view from existing decision rows only.
    """
    judge_model = normalize_model_id(judge_model)
    try:
        from backend.analysis.latent_quality import fetch_pairwise_results, compute_raw_win_rates, fit_bradley_terry
        from backend.analysis.neutralized_scores import fetch_decisions_with_lengths, run_length_bias_regression, compute_neutralized_scores

        pairwise = fetch_pairwise_results(db_engine, judge_model_name=judge_model)
        if pairwise.empty:
            return []
        models = sorted(set(pairwise["model_i"]) | set(pairwise["model_j"]))
        raw_win_rates = compute_raw_win_rates(pairwise, models)
        theta, _ = fit_bradley_terry(pairwise, models)
        bt_results = pd.DataFrame({
            "model": models,
            "raw_win_rate": [raw_win_rates[model] for model in models],
            "bt_score": theta,
        })
        bt_results["quality_tier"] = bt_results["bt_score"].map(
            lambda score: "Top Tier" if score >= 0.5 else "Competitive" if score >= 0.0 else "Below Average" if score >= -1.0 else "Weak"
        )
        neutralized_input = fetch_decisions_with_lengths(db_engine, judge_model_name=judge_model)
        if neutralized_input.empty:
            neutralized = pd.DataFrame({"model": models, "neutralized_score": 0.0})
        else:
            _, _, _, _, residuals, _, _ = run_length_bias_regression(neutralized_input)
            neutralized = compute_neutralized_scores(neutralized_input, residuals)[["model", "neutralized_score"]]
        result = bt_results.merge(neutralized, on="model", how="left")
        result["neutralized_score"] = result["neutralized_score"].fillna(0.0)
        return _df_to_records(result[["model", "raw_win_rate", "bt_score", "quality_tier", "neutralized_score"]].sort_values("bt_score", ascending=False))
    except Exception:
        logger.exception("Read-only historical leaderboard calculation failed for '%s'.", judge_model)
        return []


@app.get("/api/leaderboard", response_model=list[LeaderboardItem])
def get_leaderboard(judge_model: str = "gpt-4o-mini") -> list[dict]:
    """
    Read the stored legacy Bradley-Terry and neutralized leaderboard artifacts.
    This public endpoint never recomputes or writes artifacts.
    """
    judge_model = normalize_model_id(judge_model)
    sanitized = judge_model.replace("/", "_")
    csv_dir = ROOT_DIR / "data" / "artifacts" / "csv"
    bt_csv_path          = csv_dir / f"bradley_terry_scores_{sanitized}.csv"
    neutralized_csv_path = csv_dir / f"neutralized_scores_{sanitized}.csv"

    if not bt_csv_path.exists() or not neutralized_csv_path.exists():
        return compute_leaderboard_read_only(engine, judge_model)

    try:
        bt_df   = pd.read_csv(bt_csv_path)
        neut_df = pd.read_csv(neutralized_csv_path)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read leaderboard CSVs for '{judge_model}': {exc}",
        )

    merged = bt_df.merge(neut_df, on="model", suffixes=("_bt", "_neut"))
    raw_win_col = "raw_win_rate_bt" if "raw_win_rate_bt" in merged.columns else ("raw_win_rate_x" if "raw_win_rate_x" in merged.columns else "raw_win_rate")

    result_df = merged[[
        "model",
        raw_win_col,
        "bt_score",
        "quality_tier",
        "neutralized_score",
    ]].rename(columns={raw_win_col: "raw_win_rate"})
    result_df = result_df.sort_values("bt_score", ascending=False).reset_index(drop=True)

    return _df_to_records(result_df)


@app.get("/api/consistency")
def get_consistency_stats(db: Session = Depends(get_db), judge_model: str = "gpt-4o-mini") -> dict:
    """
    Query multi-turn logical consistency and inter-judge reliability stats for a given judge_model.
    """
    judge_model = normalize_model_id(judge_model)
    from backend.analysis.consistency import (
        fetch_decisions,
        compute_position_consistency,
        compute_cross_category_consistency,
        compute_overall_consistency_score,
        compute_inter_judge_kappa,
    )
    try:
        df = fetch_decisions(db.get_bind(), judge_model_name=judge_model)
        if df.empty:
            target_comparator = "deepseek/deepseek-chat" if judge_model == "gpt-4o-mini" else "gpt-4o-mini"
            return {
                "evidence_class": "LEGACY_EXPLORATORY",
                "status": "NO_DATA",
                "n": 0,
                "judge_model": judge_model,
                "overall_consistency_score": None,
                "position_consistency_rate": None,
                "cross_category_consistency_rate": None,
                "inconsistencies_count": None,
                "inter_judge_reliability": {
                    "inter_judge_kappa": None,
                    "overlapping_trials": 0,
                    "agreement_rate": None,
                    "model_a": judge_model,
                    "model_b": target_comparator,
                },
            }

        pos_results = compute_position_consistency(df)
        cross_cat_summary, pair_flip_counts = compute_cross_category_consistency(df)
        overall, pos_score, cat_score = compute_overall_consistency_score(pos_results, pair_flip_counts)

        target_comparator = "deepseek/deepseek-chat" if judge_model == "gpt-4o-mini" else "gpt-4o-mini"
        inter_judge = compute_inter_judge_kappa(
            db.get_bind(),
            model_a=judge_model,
            model_b=target_comparator,
        )

        return {
            "evidence_class": "LEGACY_EXPLORATORY",
            "status": "AVAILABLE",
            "n": len(df),
            "judge_model": judge_model,
            "overall_consistency_score": overall,
            "position_consistency_rate": pos_score,
            "cross_category_consistency_rate": cat_score,
            "inconsistencies_count": pos_results.get("inconsistencies", 0),
            "inter_judge_reliability": inter_judge,
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Exploratory consistency telemetry is unavailable.")


# ── GET /api/stats/bias ───────────────────────────────────────────────────────

@app.get("/api/stats/bias", response_model=BiasStatsResponse)
def get_bias_stats(db: Session = Depends(get_db), judge_model: str = "gpt-4o-mini") -> dict:
    """
    Query the database for raw data points needed by the frontend bias charts.

    Parameters
    ----------
    judge_model : str, optional
        Filter metrics by LLM judge model name (defaults to "gpt-4o-mini").

    Returns
    -------
    verbosity_data : list[dict]
        Word count differences vs LLM win verdicts
    position_data  : dict
        Total wins for Position A vs Position B vs Ties
    domain_kappa   : list[dict]
        Domain-stratified Cohen's Kappa score per category
    format_bias    : dict
        Selection counts & Chi-Square test comparing markdown_heavy vs plain_text
    """
    judge_model = normalize_model_id(judge_model)
    try:
        # ── Verbosity data ────────────────────────────────────────────────────
        verbosity_sql = text("""
            SELECT
                (a1.word_count - a2.word_count) AS word_count_diff,
                CASE
                    WHEN jd.winner_id IS NULL           THEN 0.5
                    WHEN jd.winner_id = jd.answer_a_id  THEN 1.0
                    ELSE                                     0.0
                END AS llm_verdict
            FROM judge_decisions jd
            JOIN answers a1 ON jd.answer_a_id = a1.id
            JOIN answers a2 ON jd.answer_b_id = a2.id
            WHERE jd.judge_model_name = :judge_model
        """)

        verbosity_rows = db.execute(verbosity_sql, {"judge_model": judge_model}).fetchall()

        if not verbosity_rows:
            return {
                "evidence_class": "LEGACY_EXPLORATORY",
                "status": "NO_DATA",
                "n": 0,
                "verbosity_data": [],
                "position_data": {"position_a": None, "position_b": None, "tie": None},
                "domain_kappa": [],
                "format_bias": {
                    "markdown_chosen": None, "plain_text_chosen": None,
                    "p_value": None, "p_value_adjusted": None, "chi2_stat": None,
                },
                "inter_judge_kappa": None,
            }

        verbosity_data = [
            {"word_count_diff": row.word_count_diff, "llm_verdict": row.llm_verdict}
            for row in verbosity_rows
        ]

        # ── Position data ─────────────────────────────────────────────────────
        position_sql = text("""
            SELECT
                SUM(CASE
                    WHEN jd.winner_id IS NULL                   THEN 0
                    WHEN jd.winner_id = jd.position_a_id        THEN 1
                    ELSE                                             0
                END) AS position_a,
                SUM(CASE
                    WHEN jd.winner_id IS NOT NULL
                     AND jd.winner_id != jd.position_a_id       THEN 1
                    ELSE                                             0
                END) AS position_b,
                SUM(CASE
                    WHEN jd.winner_id IS NULL                   THEN 1
                    ELSE                                             0
                END) AS tie
            FROM judge_decisions jd
            WHERE jd.judge_model_name = :judge_model
        """)

        pos_row = db.execute(position_sql, {"judge_model": judge_model}).fetchone()

        position_data = {
            "position_a": int(pos_row.position_a or 0) if pos_row else 0,
            "position_b": int(pos_row.position_b or 0) if pos_row else 0,
            "tie":        int(pos_row.tie        or 0) if pos_row else 0,
        }

        # ── Domain Kappa data ──────────────────────────────────────────────────
        domain_sql = text("""
            SELECT
                p.category AS category,
                hp.winner_id AS human_winner_id,
                hp.answer_a_id AS answer_a_id,
                hp.answer_b_id AS answer_b_id,
                jd.winner_id AS llm_winner_id
            FROM human_preferences hp
            JOIN judge_decisions jd
                ON hp.prompt_id = jd.prompt_id
                AND hp.answer_a_id = jd.answer_a_id
                AND hp.answer_b_id = jd.answer_b_id
            JOIN prompts p ON hp.prompt_id = p.id
            WHERE jd.judge_model_name = :judge_model
        """)

        domain_rows = db.execute(domain_sql, {"judge_model": judge_model}).fetchall()

        if domain_rows:
            domain_df = pd.DataFrame([
                {
                    "category": row.category,
                    "human_choice": (
                        "Tie" if row.human_winner_id is None
                        else ("A" if row.human_winner_id == row.answer_a_id else "B")
                    ),
                    "llm_choice": (
                        "Tie" if row.llm_winner_id is None
                        else ("A" if row.llm_winner_id == row.answer_a_id else "B")
                    ),
                }
                for row in domain_rows
            ])

            domain_kappa_dict = {}
            for cat, group in domain_df.groupby("category"):
                try:
                    if len(group) > 1:
                        score = float(cohen_kappa_score(group["human_choice"], group["llm_choice"]))
                        domain_kappa_dict[str(cat)] = round(score, 3) if not math.isnan(score) else None
                    else:
                        domain_kappa_dict[str(cat)] = None
                except Exception:
                    domain_kappa_dict[str(cat)] = None

            domain_kappa = [
                {"domain": cat, "kappa": score}
                for cat, score in sorted(domain_kappa_dict.items(), key=lambda x: (x[1] is not None, x[1] or 0), reverse=True)
            ]
        else:
            domain_kappa = []

        # ── Format Bias data ──────────────────────────────────────────────────
        format_sql = text("""
            SELECT
                a1.text AS text_a,
                a2.text AS text_b,
                CASE
                    WHEN jd.winner_id IS NULL           THEN 'Tie'
                    WHEN jd.winner_id = jd.answer_a_id  THEN 'A'
                    ELSE                                     'B'
                END AS llm_choice
            FROM judge_decisions jd
            JOIN answers a1 ON jd.answer_a_id = a1.id
            JOIN answers a2 ON jd.answer_b_id = a2.id
            WHERE jd.judge_model_name = :judge_model
        """)

        format_rows = db.execute(format_sql, {"judge_model": judge_model}).fetchall()

        markdown_chosen = 0
        plain_text_chosen = 0

        for row in format_rows:
            if row.llm_choice == 'Tie':
                continue
            fmt_a = _classify_format_text(row.text_a)
            fmt_b = _classify_format_text(row.text_b)

            if fmt_a != fmt_b:
                chosen_fmt = fmt_a if row.llm_choice == 'A' else fmt_b
                if chosen_fmt == 'markdown_heavy':
                    markdown_chosen += 1
                else:
                    plain_text_chosen += 1

        total_fmt_obs = markdown_chosen + plain_text_chosen
        if total_fmt_obs > 0:
            exp_fmt = [total_fmt_obs / 2, total_fmt_obs / 2]
            chi2_fmt, p_val_fmt = chisquare(f_obs=[markdown_chosen, plain_text_chosen], f_exp=exp_fmt)
            chi2_fmt = float(chi2_fmt) if not math.isnan(chi2_fmt) else 0.0
            p_val_fmt = float(p_val_fmt) if not math.isnan(p_val_fmt) else 1.0
        else:
            chi2_fmt = None
            p_val_fmt = None

        # Zero eligible mixed-format comparisons is an absence of data, not a
        # measured 0-count result. Preserve numeric zeros only when eligible
        # comparisons actually exist.
        format_bias = {
            "markdown_chosen": markdown_chosen if total_fmt_obs > 0 else None,
            "plain_text_chosen": plain_text_chosen if total_fmt_obs > 0 else None,
            "p_value": round(p_val_fmt, 6) if p_val_fmt is not None else None,
            "p_value_adjusted": round(float(_adjust_pvalues_bh([p_val_fmt])[0]), 6) if p_val_fmt is not None else None,
            "chi2_stat": round(chi2_fmt, 3) if chi2_fmt is not None else None,
        }

        # ── Inter-Judge Agreement (RQ6) ──────────────────────────────────────
        try:
            target_comparator = "deepseek/deepseek-chat" if judge_model == "gpt-4o-mini" else "gpt-4o-mini"
            inter_judge_res = compute_inter_judge_kappa(db.get_bind(), model_a=judge_model, model_b=target_comparator)
            inter_judge_kappa = inter_judge_res.get("inter_judge_kappa") if int(inter_judge_res.get("overlapping_trials") or 0) else None
        except Exception:
            inter_judge_kappa = None

        return {
            "evidence_class": "LEGACY_EXPLORATORY",
            "status": "AVAILABLE",
            "n": len(verbosity_data),
            "verbosity_data": verbosity_data,
            "position_data":  position_data,
            "domain_kappa":   domain_kappa,
            "format_bias":    format_bias,
            "inter_judge_kappa": inter_judge_kappa,
        }
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Exploratory bias telemetry is unavailable."
        )


# ── GET /api/qualitative/{bucket} ─────────────────────────────────────────────

@app.get("/api/qualitative/{bucket}")
def get_qualitative_bucket(bucket: str, judge_model: str = "gpt-4o-mini") -> list[dict]:
    """
    Return the full contents of a stratified qualitative CSV bucket.

    Parameters
    ----------
    bucket : str
        One of: "verbosity", "forced_choice", "position_bias",
        "baseline_alignment"
    judge_model : str
        The judge model whose qualitative outputs to read. Resolves to a
        model-specific subdirectory under qualitative_data/ when present;
        falls back to the root qualitative_data/ folder for backwards
        compatibility.

    Returns
    -------
    list[dict]  One dictionary per row in the requested CSV.

    Raises
    ------
    HTTPException 404  If the bucket name is invalid or the CSV file is missing.
    """
    filename = BUCKET_FILES.get(bucket)
    if filename is None:
        valid = ", ".join(f'"{b}"' for b in BUCKET_FILES)
        raise HTTPException(
            status_code=404,
            detail=(
                f'Unknown bucket "{bucket}". '
                f"Valid options are: {valid}."
            ),
        )

    # Prefer model-specific subdirectory; fall back to shared root folder
    sanitized = judge_model.replace("/", "_")
    model_specific_path = QUALITATIVE_DIR / sanitized / filename
    root_fallback_path  = QUALITATIVE_DIR / filename
    csv_path = model_specific_path if model_specific_path.exists() else root_fallback_path
    if not csv_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f'Bucket file "{filename}" not found on disk.',
        )

    df = pd.read_csv(csv_path)

    # Replace NaN values with empty strings so JSON serialization is clean
    df = df.fillna("")

    # Enrich with full prompt and candidate answer texts from database in a single batch query
    records = df.to_dict(orient="records")
    try:
        from backend.core.database import engine
        from sqlalchemy import text as sa_text, bindparam

        def _parse_pid(val: Any) -> int | None:
            if val is None or str(val).strip() == "":
                return None
            s = str(val).strip().split('.')[0]
            return int(s) if s.isdigit() else None

        pids = list({
            _parse_pid(r.get("prompt_id"))
            for r in records
            if _parse_pid(r.get("prompt_id")) is not None
        })

        if pids:
            with engine.connect() as conn:
                # Batch query prompts
                p_stmt = sa_text("SELECT id, text FROM prompts WHERE id IN :pids").bindparams(
                    bindparam("pids", expanding=True)
                )
                prompts_map = {row[0]: row[1] for row in conn.execute(p_stmt, {"pids": pids}).fetchall()}

                # Batch query answers
                a_stmt = sa_text("SELECT id, prompt_id, model_name, text FROM answers WHERE prompt_id IN :pids").bindparams(bindparam("pids", expanding=True))
                answers_map: dict[tuple[int, str], list[tuple[int, str]]] = {}
                for row in conn.execute(a_stmt, {"pids": pids}).fetchall():
                    answers_map.setdefault((row[1], row[2]), []).append((row[0], row[3]))

                for row in records:
                    pid_int = _parse_pid(row.get("prompt_id"))
                    if pid_int is not None:
                        declared = [value.strip() for value in re.split(r"\s+vs\s+", str(row.get("model_names") or ""), flags=re.IGNORECASE)]
                        answer_a = answers_map.get((pid_int, declared[0]), []) if len(declared) == 2 else []
                        answer_b = answers_map.get((pid_int, declared[1]), []) if len(declared) == 2 else []
                        if pid_int in prompts_map and len(answer_a) == len(answer_b) == 1:
                            row.update({"prompt_text": prompts_map[pid_int], "answer_a_id": answer_a[0][0], "answer_a_model": declared[0], "answer_a_text": answer_a[0][1], "answer_b_id": answer_b[0][0], "answer_b_model": declared[1], "answer_b_text": answer_b[0][1], "provenance_status": "VERIFIED"})
                        else:
                            row["provenance_status"] = "UNAVAILABLE"
                    else:
                        row["provenance_status"] = "UNAVAILABLE"

        return records
    except Exception as exc:
        print(f"Database lookup notice during qualitative enrichment: {exc}")

    return [{**row, "provenance_status": "UNAVAILABLE"} for row in _df_to_records(df)]


# ── POST /api/evaluate ────────────────────────────────────────────────────────

class EvaluateRequest(BaseModel):
    prompt: str
    answer_a: str
    answer_b: str
    model_name: str = Field(
        default="gpt-4o-mini",
        description="Model name. Supports OpenAI (e.g. 'gpt-4o-mini'), Local Ollama ('llama3'), and OpenRouter models ('deepseek/deepseek-chat', 'anthropic/claude-3.5-haiku', 'meta-llama/llama-3.3-70b-instruct')",
    )


def _validate_api_key_or_raise(model_name: str):
    """Enforce strict API key presence for cloud and OpenRouter models. Disables mock fallbacks in production."""
    if is_local_model(model_name):
        return
    if "/" in model_name:
        key = os.getenv("OPENROUTER_API_KEY")
        if not key or key.startswith("your_"):
            raise ValueError(f"OPENROUTER_API_KEY is missing or unconfigured in .env for model '{model_name}'.")
        return
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("your_"):
        raise ValueError(f"OPENAI_API_KEY is missing or unconfigured in .env for model '{model_name}'.")


def _get_or_create_prompt(db: Session, text_content: str, category: str = "live") -> int:
    """
    Get-or-create helper for prompts table to prevent UniqueViolation errors on insertion.
    1. Checks if exact prompt text exists. If found, returns existing prompt ID.
    2. Resynchronizes PostgreSQL primary key sequence if out of sync.
    3. Safely inserts new prompt letting database assign auto-increment ID.
    """
    cleaned_text = text_content[:4096]
    existing = db.execute(
        text("SELECT id FROM prompts WHERE text = :text LIMIT 1"),
        {"text": cleaned_text}
    ).fetchone()
    if existing:
        return existing[0]

    try:
        db.execute(text(
            "SELECT setval(pg_get_serial_sequence('prompts', 'id'), "
            "COALESCE((SELECT MAX(id) FROM prompts), 0) + 1, false)"
        ))
    except Exception:
        pass

    inserted = db.execute(
        text("INSERT INTO prompts (text, category) VALUES (:text, :cat) RETURNING id"),
        {"text": cleaned_text, "cat": category}
    ).fetchone()
    return inserted[0] if inserted else 1


def _insert_answer_safe(db: Session, prompt_id: int, model_name: str, text_content: str) -> int:
    """
    Safely inserts answer row for prompt, preventing sequence out-of-sync UniqueViolations.
    """
    cleaned_text = text_content[:8192]
    wc = len(cleaned_text.split())
    try:
        db.execute(text(
            "SELECT setval(pg_get_serial_sequence('answers', 'id'), "
            "COALESCE((SELECT MAX(id) FROM answers), 0) + 1, false)"
        ))
    except Exception:
        pass

    inserted = db.execute(
        text("INSERT INTO answers (prompt_id, model_name, text, word_count) "
             "VALUES (:pid, :model, :text, :wc) RETURNING id"),
        {"pid": prompt_id, "model": model_name, "text": cleaned_text, "wc": wc}
    ).fetchone()
    return inserted[0] if inserted else 1


def _insert_decision_safe(db: Session, prompt_id: int, judge_model_name: str, a_id: int, b_id: int, winner_id: int | None, reasoning_text: str):
    """
    Safely inserts judge decision row, preventing sequence out-of-sync UniqueViolations.
    """
    try:
        db.execute(text(
            "SELECT setval(pg_get_serial_sequence('judge_decisions', 'id'), "
            "COALESCE((SELECT MAX(id) FROM judge_decisions), 0) + 1, false)"
        ))
    except Exception:
        pass

    db.execute(
        text("INSERT INTO judge_decisions "
             "(prompt_id, judge_model_name, answer_a_id, answer_b_id, position_a_id, winner_id, reasoning) "
             "VALUES (:pid, :judge, :a_id, :b_id, :pos_a, :winner, :reasoning)"),
        {
            "pid": prompt_id,
            "judge": normalize_model_id(judge_model_name),
            "a_id": a_id,
            "b_id": b_id,
            "pos_a": a_id,
            "winner": winner_id,
            "reasoning": reasoning_text[:4096],
        }
    )


@app.post("/api/evaluate", response_model=EvaluateResponse)
def evaluate_judge(req: EvaluateRequest, db: Session = Depends(get_db), _: None = Depends(_require_live_sandbox_enabled)) -> dict:
    """
    Perform a live G-EVAL evaluation comparing Answer A vs Answer B.
    Enforces a strict Zero-Mock policy. Internal failures are logged server-side
    and do not expose operational details to the client.
    Results are persisted to PostgreSQL so live evaluations accumulate in the database.
    """
    if not req.prompt.strip() or not req.answer_a.strip() or not req.answer_b.strip():
        raise HTTPException(status_code=400, detail="Prompt, Answer A, and Answer B are required.")

    try:
        _validate_api_key_or_raise(req.model_name)
    except ValueError as val_err:
        logger.warning("Live evaluation is not configured", exc_info=val_err)
        raise HTTPException(status_code=503, detail="Live evaluation is not configured.") from val_err

    try:
        result = call_judge(
            client=None,
            question=req.prompt,
            answer_a=req.answer_a,
            answer_b=req.answer_b,
            model_name=req.model_name,
            temperature=0.0,
        )
        verdict = result.verdict if result.verdict in ["A", "B", "TIE", "UNKNOWN"] else "UNKNOWN"

        # Persist the live evaluation to PostgreSQL
        try:
            with db.begin_nested():
                prompt_id = _get_or_create_prompt(db, req.prompt, category="live")
                ans_a_id = _insert_answer_safe(db, prompt_id, "answer_a", req.answer_a)
                ans_b_id = _insert_answer_safe(db, prompt_id, "answer_b", req.answer_b)
                winner_id = ans_a_id if verdict == "A" else (ans_b_id if verdict == "B" else None)
                _insert_decision_safe(db, prompt_id, req.model_name, ans_a_id, ans_b_id, winner_id, result.reasoning)
                db.commit()
        except Exception as db_exc:
            db.rollback()
            logger.exception("Unable to persist live evaluation")
            raise HTTPException(status_code=500, detail="Unable to persist live evaluation.") from db_exc

        return {
            "winner": verdict,
            "verbatim_reasoning": result.reasoning,
            "model_name": req.model_name if not is_local_model(req.model_name) else f"{req.model_name} (Local / Ollama)",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Live provider request failed")
        raise HTTPException(status_code=502, detail="Provider request failed.") from exc



class CalibratedEvaluationRequest(BaseModel):
    question: str
    answer_a: str
    answer_b: str
    model_name: str = Field(
        default="gpt-4o-mini",
        description="Model name. Supports OpenAI ('gpt-4o-mini'), Local Ollama ('llama3'), and OpenRouter models ('deepseek/deepseek-chat', 'anthropic/claude-3.5-haiku', 'meta-llama/llama-3.3-70b-instruct')",
    )
    temperature: float = 0.0
    mitigation_strategy: Literal["dual_ab", "verbosity_penalized", "none"] = "dual_ab"


@app.post("/api/evaluate/calibrated", response_model=CalibratedEvaluationResponse)
def evaluate_calibrated(req: CalibratedEvaluationRequest, db: Session = Depends(get_db), _: None = Depends(_require_live_sandbox_enabled)) -> dict[str, Any]:
    """
    Execute real-time in-flight bias mitigation via Dual A/B Position Swapping or Length Penalization.
    Enforces a strict Zero-Mock policy. Internal failures are logged server-side
    and do not expose operational details to the client.
    Final calibrated verdict is persisted to PostgreSQL so live evaluations accumulate in the database.
    """
    try:
        _validate_api_key_or_raise(req.model_name)
    except ValueError as val_err:
        logger.warning("Calibrated live evaluation is not configured", exc_info=val_err)
        raise HTTPException(status_code=503, detail="Live evaluation is not configured.") from val_err

    try:
        res = call_calibrated_judge(
            client=None,
            question=req.question,
            answer_a=req.answer_a,
            answer_b=req.answer_b,
            model_name=req.model_name,
            temperature=req.temperature,
            mitigation_strategy=req.mitigation_strategy,
        )

        final_verdict = res.final_calibrated_winner

        # Persist calibrated decision to PostgreSQL
        try:
            with db.begin_nested():
                prompt_id = _get_or_create_prompt(db, req.question, category="live_calibrated")
                ans_a_id = _insert_answer_safe(db, prompt_id, "answer_a", req.answer_a)
                ans_b_id = _insert_answer_safe(db, prompt_id, "answer_b", req.answer_b)
                winner_id = ans_a_id if final_verdict == "A" else (ans_b_id if final_verdict == "B" else None)
                reasoning_blob = json.dumps(res.detailed_reasoning) if isinstance(res.detailed_reasoning, dict) else str(res.detailed_reasoning)
                _insert_decision_safe(db, prompt_id, req.model_name, ans_a_id, ans_b_id, winner_id, reasoning_blob)
                db.commit()
        except Exception as db_exc:
            db.rollback()
            logger.exception("Unable to persist live evaluation")
            raise HTTPException(status_code=500, detail="Unable to persist live evaluation.") from db_exc

        return {
            "status": "success",
            "original_order_winner": res.original_order_winner,
            "swapped_order_winner": res.swapped_order_winner,
            "final_calibrated_winner": final_verdict,
            "position_bias_detected": res.position_bias_detected,
            "detailed_reasoning": res.detailed_reasoning,
            "total_input_tokens": res.total_input_tokens,
            "total_output_tokens": res.total_output_tokens,
            "model_name": res.model_name,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Calibrated live provider request failed")
        raise HTTPException(status_code=502, detail="Provider request failed.") from exc


# ── Multi-Judge Ensemble Endpoint ──────────────────────────────────────────────

class MultiJudgeEnsembleRequest(BaseModel):
    question: str
    answer_a: str
    answer_b: str
    judge_models: list[str] = Field(
        default=["gpt-4o-mini", "deepseek/deepseek-chat", "meta-llama/llama-3.3-70b-instruct"],
        description="List of judge model identifiers for multi-judge ensemble voting",
    )
    temperature: float = 0.0
    mitigation_strategy: Literal["dual_ab", "verbosity_penalized", "none"] = "dual_ab"


class MultiJudgeEnsembleResponse(BaseModel):
    status: str
    consensus_verdict: str
    vote_counts: dict[str, int]
    individual_results: list[dict[str, Any]]
    total_models: int
    successful_models: int
    total_input_tokens: int
    total_output_tokens: int
    persisted: bool


@app.post("/api/evaluate/ensemble", response_model=MultiJudgeEnsembleResponse)
def evaluate_ensemble(req: MultiJudgeEnsembleRequest, db: Session = Depends(get_db), _: None = Depends(_require_live_sandbox_enabled)) -> dict[str, Any]:
    """
    Executes concurrent multi-judge ensemble voting across selected LLM judge models.
    Aggregates individual verdicts into a majority-rule consensus verdict.
    Persists ensemble judgment decisions to PostgreSQL for database auditability.
    """
    if not req.judge_models or len(req.judge_models) == 0:
        raise HTTPException(status_code=400, detail="At least one judge model must be provided in 'judge_models'.")

    # Validate API keys for cloud/openrouter models
    for m in req.judge_models:
        try:
            _validate_api_key_or_raise(m)
        except ValueError as val_err:
            logger.warning("Ensemble live evaluation is not configured", exc_info=val_err)
            raise HTTPException(status_code=503, detail="Live evaluation is not configured.") from val_err

    try:
        res = call_multi_judge_ensemble(
            question=req.question,
            answer_a=req.answer_a,
            answer_b=req.answer_b,
            model_names=req.judge_models,
            temperature=req.temperature,
            mitigation_strategy=req.mitigation_strategy,
        )

        persisted = True
        # Persist individual judge decisions to PostgreSQL
        try:
            with db.begin_nested():
                prompt_id = _get_or_create_prompt(db, req.question, category="ensemble_eval")
                ans_a_id = _insert_answer_safe(db, prompt_id, "answer_a", req.answer_a)
                ans_b_id = _insert_answer_safe(db, prompt_id, "answer_b", req.answer_b)

                for item in res.individual_results:
                    if item.get("status") == "success":
                        v = item.get("verdict", "UNKNOWN")
                        winner_id = ans_a_id if v == "A" else (ans_b_id if v == "B" else None)
                        reasoning_str = str(item.get("reasoning", ""))
                        _insert_decision_safe(db, prompt_id, item["model_name"], ans_a_id, ans_b_id, winner_id, reasoning_str)
                db.commit()
        except Exception:
            db.rollback()
            logger.exception("Unable to persist live ensemble evaluation")
            persisted = False

        return {
            "status": "success",
            "consensus_verdict": res.consensus_verdict,
            "vote_counts": res.vote_counts,
            "individual_results": res.individual_results,
            "total_models": res.total_models,
            "successful_models": res.successful_models,
            "total_input_tokens": res.total_input_tokens,
            "total_output_tokens": res.total_output_tokens,
            "persisted": persisted,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Live ensemble provider request failed")
        raise HTTPException(status_code=502, detail="Provider request failed.") from exc


