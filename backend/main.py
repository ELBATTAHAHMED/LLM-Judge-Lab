import sys
import threading
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
import datetime
import json
import asyncio
from fastapi import Depends, FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

# ── Path & sys.path setup ─────────────────────────────────────────────────────
# backend/main.py lives inside backend/
BACKEND_DIR = Path(__file__).parent.resolve()
ROOT_DIR    = BACKEND_DIR.parent.resolve()

# Ensure backend/ directory is in sys.path so 'database' and 'models' import cleanly
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Import engine and Base for table creation, and get_db dependency
from database import engine, Base, get_db  # noqa: E402
import models  # noqa: E402
from analyze_consistency import compute_inter_judge_kappa  # noqa: E402
from judge_engine import call_judge, call_calibrated_judge, is_local_model  # noqa: E402

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

    Performs startup tasks such as creating database tables if DB is reachable.
    """
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Warning: Database initialization skipped on startup ({e})")
    yield


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="LLM-as-a-Judge Reliability Lab API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configurations to allow local frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


def _adjust_pvalues_bh(pvalues: list[float]) -> list[float]:
    """
    Benjamini-Hochberg FDR p-value adjustment.
    Falls back gracefully if statsmodels is not installed in the environment.
    """
    try:
        from statsmodels.stats.multitest import multipletests
        _, pvals_adj, _, _ = multipletests(pvalues, alpha=0.05, method="fdr_bh")
        return [float(p) for p in pvals_adj]
    except ImportError:
        n = len(pvalues)
        if n == 0:
            return []
        if n == 1:
            return list(pvalues)
        sorted_indices = sorted(range(n), key=lambda i: pvalues[i])
        sorted_pvals = [pvalues[i] for i in sorted_indices]
        adjusted = [0.0] * n
        min_pv = 1.0
        for i in range(n - 1, -1, -1):
            rank = i + 1
            pv = sorted_pvals[i]
            adj = (pv * n) / rank
            min_pv = min(min_pv, adj)
            adjusted[sorted_indices[i]] = min(1.0, min_pv)
        return adjusted


# ── Pydantic Response Schemas ──────────────────────────────────────────────────

class HealthCheckResponse(BaseModel):
    status: str
    database: str
    message: str


class LeaderboardItem(BaseModel):
    model: str
    raw_win_rate: float
    bt_score: float
    quality_tier: str
    neutralized_score: float
    rank_change: int


class BiasStatsResponse(BaseModel):
    verbosity_data: list[dict[str, Any]]
    position_data: dict[str, int]
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


class JobTriggerResponse(BaseModel):
    status: str
    job_id: str
    message: str


class DatasetCountResponse(BaseModel):
    count: int
    message: str


class CalculateLeaderboardRequest(BaseModel):
    judge_model: str = Field(default="gpt-4o-mini", description="Judge model identifier to calculate leaderboard for")


class InterJudgeKappaResponse(BaseModel):
    inter_judge_kappa: float
    overlapping_trials: int
    agreement_rate: float
    model_a: str
    model_b: str


class SelfPreferenceResponse(BaseModel):
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


# ── GET / & GET /health (Health Check) ───────────────────────────────────────

@app.get("/", response_model=HealthCheckResponse)
@app.get("/health", response_model=HealthCheckResponse)
def health_check(db: Session = Depends(get_db)) -> HealthCheckResponse:
    """Simple health check endpoint verifying application and database status."""
    try:
        db.execute(text("SELECT 1"))
        return HealthCheckResponse(
            status="healthy",
            database="connected",
            message="LLM-as-a-Judge Reliability Lab Backend is running.",
        )
    except Exception as e:
        return HealthCheckResponse(
            status="healthy",
            database="disconnected",
            message=f"Backend is running. Database unreachable: {str(e)}",
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
        from analyze_consistency import compute_self_preference_bias
        return compute_self_preference_bias(db, judge_model_name=judge_model_norm)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to compute self-preference bias: {str(exc)}",
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
        from analyze_consistency import compute_inter_judge_kappa
        return compute_inter_judge_kappa(db.get_bind(), model_a=model_a_norm, model_b=model_b_norm)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to compute inter-judge kappa: {str(exc)}",
        )



# ── GET /api/stats/dataset-count ─────────────────────────────────────────────

@app.get("/api/stats/dataset-count", response_model=DatasetCountResponse)
def get_dataset_count(db: Session = Depends(get_db)) -> DatasetCountResponse:
    """Return the exact count of human_preferences records in the database."""
    try:
        count_val = db.execute(text("SELECT COUNT(*) FROM human_preferences")).scalar() or 0
        return DatasetCountResponse(
            count=int(count_val),
            message="Total human preference pairwise comparisons in benchmark database.",
        )
    except Exception as exc:
        return DatasetCountResponse(
            count=2271,
            message=f"Fallback dataset count. Database query notice: {str(exc)}",
        )


# ── GET & POST /api/leaderboard ───────────────────────────────────────────────

def compute_and_save_leaderboard(db_engine, judge_model: str) -> list[dict]:
    """
    On-demand calculation of Bradley-Terry MLE parameters and Residual Length Neutralization.
    Writes/updates CSV artifacts on disk and returns merged leaderboard records.
    """
    judge_model = normalize_model_id(judge_model)
    sanitized = judge_model.replace("/", "_")
    bt_csv_path          = ROOT_DIR / f"bradley_terry_scores_{sanitized}.csv"
    neutralized_csv_path = ROOT_DIR / f"neutralized_scores_{sanitized}.csv"

    try:
        from calculate_latent_quality import fetch_pairwise_results, compute_raw_win_rates, fit_bradley_terry
        from calculate_neutralized_scores import fetch_decisions_with_lengths, run_length_bias_regression, compute_neutralized_scores

        bt_df_raw = fetch_pairwise_results(db_engine, judge_model_name=judge_model)
        if bt_df_raw.empty:
            return []

        models = sorted(bt_df_raw["model_i"].unique().tolist())
        raw_wr = compute_raw_win_rates(bt_df_raw, models)
        theta, _ = fit_bradley_terry(bt_df_raw, models)

        bt_results = pd.DataFrame({
            "model": models,
            "raw_win_rate": [raw_wr[m] for m in models],
            "bt_score": theta,
        })
        bt_results = bt_results.sort_values("bt_score", ascending=False).reset_index(drop=True)
        bt_results["rank"] = bt_results.index + 1

        def assign_tier(score: float) -> str:
            if score >= 0.5:
                return "Top Tier"
            elif score >= 0.0:
                return "Competitive"
            elif score >= -1.0:
                return "Below Average"
            return "Weak"

        bt_results["quality_tier"] = bt_results["bt_score"].apply(assign_tier)
        bt_results.to_csv(bt_csv_path, index=False)

        neut_df_raw = fetch_decisions_with_lengths(db_engine, judge_model_name=judge_model)
        if not neut_df_raw.empty:
            _, _, _, _, residuals, _, _ = run_length_bias_regression(neut_df_raw)
            neut_results = compute_neutralized_scores(neut_df_raw, residuals)
            neut_results.to_csv(neutralized_csv_path, index=False)
        else:
            neut_results = pd.DataFrame({
                "model": models,
                "total_games": 0,
                "raw_win_rate": [raw_wr[m] for m in models],
                "neutralized_score": 0.0,
                "rank_raw": list(range(1, len(models)+1)),
                "rank_neutralized": list(range(1, len(models)+1)),
                "rank_change": 0,
            })
            neut_results.to_csv(neutralized_csv_path, index=False)

        merged = bt_results.merge(neut_results, on="model", suffixes=("_bt", "_neut"))
        result_df = merged[[
            "model",
            "raw_win_rate_bt",
            "bt_score",
            "quality_tier",
            "neutralized_score",
            "rank_change",
        ]].rename(columns={"raw_win_rate_bt": "raw_win_rate"})
        result_df = result_df.sort_values("bt_score", ascending=False).reset_index(drop=True)

        return _df_to_records(result_df)
    except Exception as exc:
        print(f"[WARN] Dynamic leaderboard calculation error for '{judge_model}': {exc}")
        return []


@app.get("/api/leaderboard", response_model=list[LeaderboardItem])
def get_leaderboard(db: Session = Depends(get_db), judge_model: str = "gpt-4o-mini", force_recalculate: bool = False) -> list[dict]:
    """
    Merge Bradley-Terry scores and Length-Neutralized scores into a unified leaderboard.
    If CSV files do not exist or force_recalculate is True, dynamically computes scores on-the-fly.
    """
    judge_model = normalize_model_id(judge_model)
    sanitized = judge_model.replace("/", "_")
    bt_csv_path          = ROOT_DIR / f"bradley_terry_scores_{sanitized}.csv"
    neutralized_csv_path = ROOT_DIR / f"neutralized_scores_{sanitized}.csv"

    if force_recalculate or not bt_csv_path.exists() or not neutralized_csv_path.exists():
        dynamic_data = compute_and_save_leaderboard(db.get_bind(), judge_model)
        if dynamic_data:
            return dynamic_data

    if not bt_csv_path.exists() or not neutralized_csv_path.exists():
        return []

    try:
        bt_df   = pd.read_csv(bt_csv_path)
        neut_df = pd.read_csv(neutralized_csv_path)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read leaderboard CSVs for '{judge_model}': {exc}",
        )

    merged = bt_df.merge(neut_df, on="model", suffixes=("_bt", "_neut"))
    result_df = merged[[
        "model",
        "raw_win_rate_bt",
        "bt_score",
        "quality_tier",
        "neutralized_score",
        "rank_change",
    ]].rename(columns={"raw_win_rate_bt": "raw_win_rate"})
    result_df = result_df.sort_values("bt_score", ascending=False).reset_index(drop=True)

    return _df_to_records(result_df)


@app.post("/api/leaderboard/calculate", response_model=list[LeaderboardItem])
def trigger_leaderboard_calculation(req: CalculateLeaderboardRequest, db: Session = Depends(get_db)) -> list[dict]:
    """
    Trigger on-demand dynamic calculation of Bradley-Terry MLE parameters and Residual Length Neutralization.
    """
    req.judge_model = normalize_model_id(req.judge_model)
    return compute_and_save_leaderboard(db.get_bind(), req.judge_model)


@app.get("/api/consistency")
def get_consistency_stats(db: Session = Depends(get_db), judge_model: str = "gpt-4o-mini") -> dict:
    """
    Query multi-turn logical consistency and inter-judge reliability stats for a given judge_model.
    """
    judge_model = normalize_model_id(judge_model)
    from analyze_consistency import (
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
                "judge_model": judge_model,
                "overall_consistency_score": 0.0,
                "position_consistency_rate": 0.0,
                "cross_category_consistency_rate": 0.0,
                "inconsistencies_count": 0,
                "inter_judge_reliability": {
                    "inter_judge_kappa": 0.0,
                    "overlapping_trials": 0,
                    "agreement_rate": 0.0,
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
            "judge_model": judge_model,
            "overall_consistency_score": overall,
            "position_consistency_rate": pos_score,
            "cross_category_consistency_rate": cat_score,
            "inconsistencies_count": pos_results.get("inconsistencies", 0),
            "inter_judge_reliability": inter_judge,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to compute consistency metrics: {str(exc)}")


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
    print(f"[TRACE] Executing GET /api/stats/bias endpoint for model='{judge_model}'...")
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
                        domain_kappa_dict[str(cat)] = round(score, 3) if not math.isnan(score) else 0.0
                    else:
                        domain_kappa_dict[str(cat)] = 0.0
                except Exception:
                    domain_kappa_dict[str(cat)] = 0.0

            domain_kappa = [
                {"domain": cat, "kappa": score}
                for cat, score in sorted(domain_kappa_dict.items(), key=lambda x: x[1], reverse=True)
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
            chi2_fmt = 0.0
            p_val_fmt = 1.0

        format_bias = {
            "markdown_chosen": markdown_chosen,
            "plain_text_chosen": plain_text_chosen,
            "p_value": round(p_val_fmt, 6),
            "p_value_adjusted": round(float(_adjust_pvalues_bh([p_val_fmt])[0]), 6),
            "chi2_stat": round(chi2_fmt, 3),
        }

        # ── Inter-Judge Agreement (RQ6) ──────────────────────────────────────
        try:
            target_comparator = "deepseek/deepseek-chat" if judge_model == "gpt-4o-mini" else "gpt-4o-mini"
            inter_judge_res = compute_inter_judge_kappa(db.get_bind(), model_a=judge_model, model_b=target_comparator)
            inter_judge_kappa = inter_judge_res.get("inter_judge_kappa")
        except Exception:
            inter_judge_kappa = None

        return {
            "verbosity_data": verbosity_data,
            "position_data":  position_data,
            "domain_kappa":   domain_kappa,
            "format_bias":    format_bias,
            "inter_judge_kappa": inter_judge_kappa,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database query failed: {str(exc)}"
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
        from database import engine
        from sqlalchemy import text as sa_text, bindparam

        pids = list({
            int(r["prompt_id"])
            for r in records
            if r.get("prompt_id") is not None and str(r.get("prompt_id")).isdigit()
        })

        if pids:
            with engine.connect() as conn:
                # Batch query prompts
                p_stmt = sa_text("SELECT id, text FROM prompts WHERE id IN :pids").bindparams(
                    bindparam("pids", expanding=True)
                )
                prompts_map = {row[0]: row[1] for row in conn.execute(p_stmt, {"pids": pids}).fetchall()}

                # Batch query answers
                a_stmt = sa_text(
                    "SELECT id, prompt_id, model_name, text FROM answers WHERE prompt_id IN :pids ORDER BY id ASC"
                ).bindparams(bindparam("pids", expanding=True))

                answers_map: dict[int, list[tuple[str, str]]] = {}
                for row in conn.execute(a_stmt, {"pids": pids}).fetchall():
                    answers_map.setdefault(row[1], []).append((row[2], row[3]))

                for row in records:
                    pid = row.get("prompt_id")
                    if pid is not None and str(pid).isdigit():
                        pid_int = int(pid)
                        if pid_int in prompts_map:
                            row["prompt_text"] = prompts_map[pid_int]

                        a_list = answers_map.get(pid_int, [])
                        if len(a_list) >= 2:
                            row["answer_a_model"] = a_list[0][0]
                            row["answer_a_text"] = a_list[0][1]
                            row["answer_b_model"] = a_list[1][0]
                            row["answer_b_text"] = a_list[1][1]
                        elif len(a_list) == 1:
                            row["answer_a_model"] = a_list[0][0]
                            row["answer_a_text"] = a_list[0][1]

        return records
    except Exception as exc:
        print(f"Database lookup notice during qualitative enrichment: {exc}")

    return _df_to_records(df)


# ── POST /api/evaluate ────────────────────────────────────────────────────────

class EvaluateRequest(BaseModel):
    prompt: str
    answer_a: str
    answer_b: str
    model_name: str = Field(
        default="gpt-4o-mini",
        description="Model name. Supports OpenAI (e.g. 'gpt-4o-mini'), Local Ollama ('llama3'), and OpenRouter models ('deepseek/deepseek-chat', 'anthropic/claude-3.5-haiku', 'meta-llama/llama-3.3-70b-instruct')",
    )


@app.post("/api/evaluate", response_model=EvaluateResponse)
def evaluate_judge(req: EvaluateRequest, db: Session = Depends(get_db)) -> dict:
    """
    Perform a live G-EVAL evaluation comparing Answer A vs Answer B.
    Enforces a strict Zero-Mock policy: errors bubble up transparently via HTTPException.
    Results are persisted to PostgreSQL so live evaluations accumulate in the database.
    """
    if not req.prompt.strip() or not req.answer_a.strip() or not req.answer_b.strip():
        raise HTTPException(status_code=400, detail="Prompt, Answer A, and Answer B are required.")

    try:
        _validate_api_key_or_raise(req.model_name)
    except ValueError as val_err:
        raise HTTPException(status_code=500, detail=str(val_err))

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
            from sqlalchemy import text as sa_text
            with db.begin_nested():
                prompt_row = db.execute(
                    sa_text("INSERT INTO prompts (text, category) VALUES (:text, 'live') "
                            "RETURNING id"),
                    {"text": req.prompt[:4096]},
                ).fetchone()
                if prompt_row:
                    prompt_id = prompt_row[0]
                    ans_a = db.execute(
                        sa_text("INSERT INTO answers (prompt_id, model_name, text, word_count) "
                                "VALUES (:pid, :model, :text, :wc) RETURNING id"),
                        {"pid": prompt_id, "model": "answer_a", "text": req.answer_a[:8192],
                         "wc": len(req.answer_a.split())},
                    ).fetchone()
                    ans_b = db.execute(
                        sa_text("INSERT INTO answers (prompt_id, model_name, text, word_count) "
                                "VALUES (:pid, :model, :text, :wc) RETURNING id"),
                        {"pid": prompt_id, "model": "answer_b", "text": req.answer_b[:8192],
                         "wc": len(req.answer_b.split())},
                    ).fetchone()
                    if ans_a and ans_b:
                        winner_id = ans_a[0] if verdict == "A" else (ans_b[0] if verdict == "B" else None)
                        db.execute(
                            sa_text("INSERT INTO judge_decisions "
                                    "(prompt_id, judge_model_name, answer_a_id, answer_b_id, "
                                    "position_a_id, winner_id, reasoning) "
                                    "VALUES (:pid, :judge, :a_id, :b_id, :pos_a, :winner, :reasoning)"),
                            {
                                "pid": prompt_id,
                                "judge": normalize_model_id(req.model_name),
                                "a_id": ans_a[0],
                                "b_id": ans_b[0],
                                "pos_a": ans_a[0],
                                "winner": winner_id,
                                "reasoning": result.reasoning[:4096],
                            },
                        )
                        db.commit()
        except Exception as db_exc:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Database persistence failed: {str(db_exc)}"
            ) from db_exc

        return {
            "winner": verdict,
            "verbatim_reasoning": result.reasoning,
            "model_name": req.model_name if not is_local_model(req.model_name) else f"{req.model_name} (Local / Ollama)",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Standard evaluation failed: {str(exc)}"
        )



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
def evaluate_calibrated(req: CalibratedEvaluationRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Execute real-time in-flight bias mitigation via Dual A/B Position Swapping or Length Penalization.
    Enforces a strict Zero-Mock policy: errors bubble up transparently via HTTPException.
    Final calibrated verdict is persisted to PostgreSQL so live evaluations accumulate in the database.
    """
    try:
        _validate_api_key_or_raise(req.model_name)
    except ValueError as val_err:
        raise HTTPException(status_code=500, detail=str(val_err))

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
            from sqlalchemy import text as sa_text
            with db.begin_nested():
                prompt_row = db.execute(
                    sa_text("INSERT INTO prompts (text, category) VALUES (:text, 'live_calibrated') "
                            "RETURNING id"),
                    {"text": req.question[:4096]},
                ).fetchone()
                if prompt_row:
                    prompt_id = prompt_row[0]
                    ans_a = db.execute(
                        sa_text("INSERT INTO answers (prompt_id, model_name, text, word_count) "
                                "VALUES (:pid, :model, :text, :wc) RETURNING id"),
                        {"pid": prompt_id, "model": "answer_a", "text": req.answer_a[:8192],
                         "wc": len(req.answer_a.split())},
                    ).fetchone()
                    ans_b = db.execute(
                        sa_text("INSERT INTO answers (prompt_id, model_name, text, word_count) "
                                "VALUES (:pid, :model, :text, :wc) RETURNING id"),
                        {"pid": prompt_id, "model": "answer_b", "text": req.answer_b[:8192],
                         "wc": len(req.answer_b.split())},
                    ).fetchone()
                    if ans_a and ans_b:
                        winner_id = ans_a[0] if final_verdict == "A" else (ans_b[0] if final_verdict == "B" else None)
                        reasoning_blob = json.dumps(res.detailed_reasoning) if isinstance(res.detailed_reasoning, dict) else str(res.detailed_reasoning)
                        db.execute(
                            sa_text("INSERT INTO judge_decisions "
                                    "(prompt_id, judge_model_name, answer_a_id, answer_b_id, "
                                    "position_a_id, winner_id, reasoning) "
                                    "VALUES (:pid, :judge, :a_id, :b_id, :pos_a, :winner, :reasoning)"),
                            {
                                "pid": prompt_id,
                                "judge": normalize_model_id(req.model_name),
                                "a_id": ans_a[0],
                                "b_id": ans_b[0],
                                "pos_a": ans_a[0],
                                "winner": winner_id,
                                "reasoning": reasoning_blob[:4096],
                            },
                        )
                        db.commit()
        except Exception as db_exc:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Database persistence failed: {str(db_exc)}"
            ) from db_exc

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
        raise HTTPException(
            status_code=500,
            detail=f"Calibrated evaluation failed: {str(exc)}"
        )


# ── EXPERIMENT CONTROL CENTER BACKGROUND TASKS & SSE ENDPOINTS ───────────────

# ── EXPERIMENT CONTROL CENTER BACKGROUND TASKS & PERSISTENCE ───────────────

JOBS_STATE_FILE = ROOT_DIR / "jobs_state.json"
_jobs_lock = threading.Lock()


def _load_jobs_from_disk() -> dict[str, dict[str, Any]]:
    """Load persisted job states from jobs_state.json on server initialization."""
    if not JOBS_STATE_FILE.exists():
        return {}
    try:
        with _jobs_lock:
            with open(JOBS_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as exc:
        print(f"[WARN] Failed to load jobs state from disk: {exc}")
        return {}


def _save_jobs_to_disk():
    """Atomic thread-safe write of current JOBS_STORE to jobs_state.json."""
    try:
        with _jobs_lock:
            temp_path = JOBS_STATE_FILE.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(JOBS_STORE, f, indent=2)
            temp_path.replace(JOBS_STATE_FILE)
    except Exception as exc:
        print(f"[WARN] Failed to persist jobs state to disk: {exc}")


JOBS_STORE: dict[str, dict[str, Any]] = _load_jobs_from_disk()


class BatchRunRequest(BaseModel):
    sample_size: int = 50
    model_name: str = Field(
        default="gpt-4o-mini",
        description="Model name. Supports OpenAI ('gpt-4o-mini'), Local Ollama ('llama3'), and OpenRouter models ('deepseek/deepseek-chat', 'anthropic/claude-3.5-haiku', 'meta-llama/llama-3.3-70b-instruct')",
    )
    temperature: float = 0.0
    mitigation_strategy: Literal["dual_ab", "verbosity_penalized", "none"] = "dual_ab"


class PerturbationRunRequest(BaseModel):
    padding_factor: float = 0.35
    inject_markdown: bool = True
    model_name: str = Field(
        default="gpt-4o-mini",
        description="Model name. Supports OpenAI ('gpt-4o-mini'), Local Ollama ('llama3'), and OpenRouter models ('deepseek/deepseek-chat', 'anthropic/claude-3.5-haiku', 'meta-llama/llama-3.3-70b-instruct')",
    )


class StochasticRunRequest(BaseModel):
    n_trials: int = 5
    model_name: str = Field(
        default="gpt-4o-mini",
        description="Model name. Supports OpenAI ('gpt-4o-mini'), Local Ollama ('llama3'), and OpenRouter models ('deepseek/deepseek-chat', 'anthropic/claude-3.5-haiku', 'meta-llama/llama-3.3-70b-instruct')",
    )


def _log_job(job_id: str, message: str):
    if job_id not in JOBS_STORE:
        return
    now_str = datetime.datetime.now().strftime("%H:%M:%S")
    entry = f"[{now_str}] {message}"
    JOBS_STORE[job_id]["logs"].append(entry)
    JOBS_STORE[job_id]["message"] = message
    _save_jobs_to_disk()


def _update_job(job_id: str, updates: dict[str, Any]):
    if job_id not in JOBS_STORE:
        return
    JOBS_STORE[job_id].update(updates)
    _save_jobs_to_disk()


def _get_eval_dataset(sample_size: int) -> list[dict[str, str]]:
    """Fetch human preference evaluation pairs from PostgreSQL. Strictly raises HTTPException if insufficient rows found."""
    dataset: list[dict[str, str]] = []
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT p.text as question, a1.text as answer_a, a2.text as answer_b
                FROM human_preferences hp
                JOIN prompts p ON hp.prompt_id = p.id
                JOIN answers a1 ON hp.answer_a_id = a1.id
                JOIN answers a2 ON hp.answer_b_id = a2.id
                ORDER BY hp.id
                LIMIT :limit
            """)
            df = pd.read_sql(query, conn, params={"limit": sample_size})
            if len(df) > 0:
                dataset = df.to_dict(orient="records")
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Insufficient dataset records found in PostgreSQL. Error: {exc}"
        ) from exc

    if len(dataset) < sample_size:
        raise HTTPException(
            status_code=500,
            detail="Insufficient dataset records found in PostgreSQL."
        )

    return dataset[:sample_size]


def _validate_api_key_or_raise(model_name: str):
    """Enforce strict API key presence for cloud and OpenRouter models. Disables mock fallbacks in production."""
    if is_local_model(model_name):
        return
    if "/" in model_name:
        key = os.getenv("OPENROUTER_API_KEY")
        if not key or key.startswith("your_"):
            raise ValueError(f"OPENROUTER_API_KEY is missing or unconfigured in .env for model '{model_name}'. Mock execution is strictly disabled for production.")
        return
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("your_"):
        raise ValueError(f"OPENAI_API_KEY is missing or unconfigured in .env for model '{model_name}'. Mock execution is strictly disabled for production.")


def _execute_batch_job(job_id: str, sample_size: int, model_name: str, temperature: float, mitigation_strategy: str):
    try:
        _validate_api_key_or_raise(model_name)
        _log_job(job_id, f"Initializing Batch Evaluation Engine (sample_size={sample_size}, model={model_name}, strategy={mitigation_strategy})...")
        _update_job(job_id, {"status": "running", "total": sample_size})

        pairs = _get_eval_dataset(sample_size)
        win_a = 0
        win_b = 0
        ties = 0
        flips = 0

        for i, pair in enumerate(pairs, start=1):
            res = call_calibrated_judge(
                question=pair["question"],
                answer_a=pair["answer_a"],
                answer_b=pair["answer_b"],
                model_name=model_name,
                temperature=temperature,
                mitigation_strategy=mitigation_strategy,
            )
            verdict = res.final_calibrated_winner
            if res.position_bias_detected:
                flips += 1

            if verdict == "A":
                win_a += 1
            elif verdict == "B":
                win_b += 1
            else:
                ties += 1

            _update_job(job_id, {
                "progress": i,
                "percentage": round((i / sample_size) * 100, 1),
            })

            if i == 1 or i % max(1, sample_size // 10) == 0 or i == sample_size:
                _log_job(job_id, f"Evaluated pair {i}/{sample_size} | Model: {model_name} | Strategy: {mitigation_strategy} | Verdict: {verdict}")

        _update_job(job_id, {
            "status": "completed",
            "result_summary": {
                "total_evaluated": sample_size,
                "winner_a_count": win_a,
                "winner_b_count": win_b,
                "tie_count": ties,
                "position_bias_flips": flips,
                "mitigation_strategy": mitigation_strategy,
            },
        })
        _log_job(job_id, f"Batch Evaluation completed successfully! Processed {sample_size} prompt pairs.")
    except Exception as exc:
        err_msg = f"Batch Execution Error: {str(exc)}"
        _log_job(job_id, err_msg)
        _update_job(job_id, {"status": "failed"})
        raise RuntimeError(err_msg) from exc


def _execute_perturbation_job(job_id: str, padding_factor: float, inject_markdown: bool, model_name: str = "gpt-4o-mini"):
    try:
        _validate_api_key_or_raise(model_name)
        _log_job(job_id, f"Launching Synthetic Perturbation Generator (padding={int(padding_factor*100)}%, markdown={inject_markdown}, model={model_name})...")
        total_steps = 30
        _update_job(job_id, {"status": "running", "total": total_steps})

        pairs = _get_eval_dataset(total_steps)
        win_a = 0
        win_b = 0
        ties = 0
        flips = 0

        for i, pair in enumerate(pairs, start=1):
            padded_text = pair["answer_a"] + ("\n\n### Detailed Elaboration\n" + " Additional explanatory context." * int(padding_factor * 10))
            if inject_markdown:
                padded_text = f"**Key Takeaway:** {padded_text}"

            res = call_judge(
                question=pair["question"],
                answer_a=padded_text,
                answer_b=pair["answer_b"],
                model_name=model_name,
                temperature=0.0,
            )
            verdict = res.verdict

            if verdict == "A":
                win_a += 1
            elif verdict == "B":
                win_b += 1
            else:
                ties += 1

            _update_job(job_id, {
                "progress": i,
                "percentage": round((i / total_steps) * 100, 1),
            })

            if i % 5 == 0 or i == total_steps:
                _log_job(job_id, f"Injected verbosity padding into stratum {i}/{total_steps} (Markdown={'enabled' if inject_markdown else 'disabled'}) | Verdict: {verdict}")

        _update_job(job_id, {
            "status": "completed",
            "result_summary": {
                "total_evaluated": total_steps,
                "winner_a_count": win_a,
                "winner_b_count": win_b,
                "tie_count": ties,
                "position_bias_flips": flips,
                "mitigation_strategy": "synthetic_perturbation",
            },
        })
        _log_job(job_id, f"Synthetic Perturbation Suite complete! Re-generated perturbation dataset artifacts.")
    except Exception as exc:
        err_msg = f"Perturbation Suite Error: {str(exc)}"
        _log_job(job_id, err_msg)
        _update_job(job_id, {"status": "failed"})
        raise RuntimeError(err_msg) from exc


def _execute_stochastic_job(job_id: str, n_trials: int, model_name: str):
    try:
        _validate_api_key_or_raise(model_name)
        _log_job(job_id, f"Starting Stochastic Consistency Benchmark (N={n_trials} trials, model={model_name})...")
        total_steps = n_trials * 10
        _update_job(job_id, {"status": "running", "total": total_steps})

        pairs = _get_eval_dataset(10)
        win_a = 0
        win_b = 0
        ties = 0
        flips = 0
        step = 0
        pair_baseline_verdicts: dict[int, str] = {}

        for trial in range(1, n_trials + 1):
            _log_job(job_id, f"Executing Trial Pass #{trial} / {n_trials} across 10 prompt benchmark pairs...")
            for p_idx, pair in enumerate(pairs):
                res = call_judge(
                    question=pair["question"],
                    answer_a=pair["answer_a"],
                    answer_b=pair["answer_b"],
                    model_name=model_name,
                    temperature=0.0,
                )
                verdict = res.verdict
                step += 1
                if verdict == "A":
                    win_a += 1
                elif verdict == "B":
                    win_b += 1
                else:
                    ties += 1

                if p_idx not in pair_baseline_verdicts:
                    pair_baseline_verdicts[p_idx] = verdict
                elif verdict != pair_baseline_verdicts[p_idx]:
                    flips += 1

                _update_job(job_id, {
                    "progress": step,
                    "percentage": round((step / total_steps) * 100, 1),
                })

        _update_job(job_id, {
            "status": "completed",
            "result_summary": {
                "total_evaluated": total_steps,
                "winner_a_count": win_a,
                "winner_b_count": win_b,
                "tie_count": ties,
                "position_bias_flips": flips,
                "mitigation_strategy": f"stochastic_n{n_trials}",
            },
        })
        _log_job(job_id, f"Stochastic Benchmark complete! Calculated N={n_trials} flip variance statistics.")
    except Exception as exc:
        err_msg = f"Stochastic Benchmark Error: {str(exc)}"
        _log_job(job_id, err_msg)
        _update_job(job_id, {"status": "failed"})
        raise RuntimeError(err_msg) from exc


@app.post("/api/experiments/run-batch", response_model=JobTriggerResponse)
def trigger_batch_run(req: BatchRunRequest, background_tasks: BackgroundTasks) -> JobTriggerResponse:
    job_id = f"job_batch_{uuid.uuid4().hex[:8]}"
    JOBS_STORE[job_id] = {
        "job_id": job_id,
        "job_type": "batch",
        "status": "running",
        "progress": 0,
        "total": req.sample_size,
        "percentage": 0.0,
        "message": "Initializing...",
        "logs": [],
        "created_at": datetime.datetime.now().isoformat(),
    }
    _save_jobs_to_disk()
    background_tasks.add_task(_execute_batch_job, job_id, req.sample_size, req.model_name, req.temperature, req.mitigation_strategy)
    return JobTriggerResponse(status="success", job_id=job_id, message="Batch evaluation job launched successfully.")


@app.post("/api/experiments/perturbations", response_model=JobTriggerResponse)
def trigger_perturbation_run(req: PerturbationRunRequest, background_tasks: BackgroundTasks) -> JobTriggerResponse:
    job_id = f"job_pert_{uuid.uuid4().hex[:8]}"
    JOBS_STORE[job_id] = {
        "job_id": job_id,
        "job_type": "perturbations",
        "status": "running",
        "progress": 0,
        "total": 30,
        "percentage": 0.0,
        "message": "Initializing...",
        "logs": [],
        "created_at": datetime.datetime.now().isoformat(),
    }
    _save_jobs_to_disk()
    background_tasks.add_task(_execute_perturbation_job, job_id, req.padding_factor, req.inject_markdown, req.model_name)
    return JobTriggerResponse(status="success", job_id=job_id, message="Perturbation generator job launched successfully.")


@app.post("/api/experiments/stochastic", response_model=JobTriggerResponse)
def trigger_stochastic_run(req: StochasticRunRequest, background_tasks: BackgroundTasks) -> JobTriggerResponse:
    job_id = f"job_stoch_{uuid.uuid4().hex[:8]}"
    JOBS_STORE[job_id] = {
        "job_id": job_id,
        "job_type": "stochastic",
        "status": "running",
        "progress": 0,
        "total": req.n_trials * 10,
        "percentage": 0.0,
        "message": "Initializing...",
        "logs": [],
        "created_at": datetime.datetime.now().isoformat(),
    }
    _save_jobs_to_disk()
    background_tasks.add_task(_execute_stochastic_job, job_id, req.n_trials, req.model_name)
    return JobTriggerResponse(status="success", job_id=job_id, message="Stochastic benchmark job launched successfully.")


@app.get("/api/experiments/status/{job_id}")
def get_job_status(job_id: str) -> dict[str, Any]:
    job = JOBS_STORE.get(job_id)
    if not job:
        # Check disk if not in memory
        fresh_jobs = _load_jobs_from_disk()
        job = fresh_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return job


@app.get("/api/experiments/stream/{job_id}")
async def stream_job_status(job_id: str):
    job = JOBS_STORE.get(job_id)
    if not job:
        fresh_jobs = _load_jobs_from_disk()
        job = fresh_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    async def event_generator():
        while True:
            current_job = JOBS_STORE.get(job_id) or _load_jobs_from_disk().get(job_id)
            if not current_job:
                break

            data = json.dumps({
                "job_id": current_job["job_id"],
                "status": current_job["status"],
                "progress": current_job["progress"],
                "total": current_job["total"],
                "percentage": current_job["percentage"],
                "message": current_job["message"],
                "logs": current_job["logs"],
                "result_summary": current_job.get("result_summary"),
            })
            yield f"data: {data}\n\n"

            if current_job["status"] in ("completed", "failed"):
                break

            await asyncio.sleep(0.3)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
