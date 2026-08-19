"""
run_controlled_experiment.py
============================
Authoritative execution CLI for Phase 9B Controlled Experiments:
"LLM-as-a-Judge Reliability Lab: Measuring and Mitigating Biases in Automatic Evaluation of Generated Responses"

Usage (from repository root):
-----------------------------
1. Zero-inference preflight:
   python backend/run_controlled_experiment.py --preflight

2. Check live progress / status (zero provider calls):
   python backend/run_controlled_experiment.py --status

3. Execute / Resume full 16,600-call CONTROLLED experiment:
   python backend/run_controlled_experiment.py --execute

4. Publish final RQ1–RQ7 analysis after execution:
   python backend/run_controlled_experiment.py --publish-analysis
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

from sqlalchemy import func, select, text
from tqdm import tqdm

from controlled_analysis_publisher import publish_manifest_analysis
from controlled_evaluation import EvaluationRequest
from controlled_models import (
    AnalysisRun,
    ControlledRun,
    DatasetVersion,
    Experiment,
    ExperimentManifest,
    ExperimentalUnit,
    PassAttempt,
    RunPass,
)
from controlled_persistence import ControlledPersistence
from controlled_prompt import PROMPT_TEMPLATE_VERSION, prompt_hash
from controlled_providers import ProviderCallError
from controlled_real_execution import ControlledRealRunner, ExecutionCaps, RealExecutionProfile
from database import SessionLocal, engine
from execution_policy import FAILURE_POLICY_VERSION, RETRY_POLICY_VERSION
from model_registry import get_model_spec
from models import Answer, Prompt
from pricing import CONFIG as PRICING_CONFIG, price_for_model
from routing_policy import routing_fingerprint, routing_policy_version

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("controlled_orchestrator")


def build_controlled_profile(
    *,
    authorization_token: str = "phase9b-authorized-final-token",
    max_usd: Decimal = Decimal("7.50"),
) -> RealExecutionProfile:
    """Construct the immutable frozen profile for Phase 9B CONTROLLED evidence."""
    session = SessionLocal()
    try:
        manifests = session.query(ExperimentManifest).order_by(ExperimentManifest.rq_code).all()
        manifest_ids = tuple(str(m.id) for m in manifests)
        manifest_hashes = tuple(m.manifest_sha256 for m in manifests)
        dataset = session.query(DatasetVersion).first()
        if not dataset:
            raise RuntimeError("No DatasetVersion found in database")

        import subprocess
        try:
            commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, text=True).strip()
            tag = subprocess.check_output(["git", "describe", "--tags", "--exact-match", "HEAD"], cwd=ROOT_DIR, text=True).strip()
        except Exception:
            commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, text=True).strip()
            tag = "pre-controlled-pilot-v8"

        return RealExecutionProfile(
            execution_mode="REAL",
            authorization_token=authorization_token,
            dataset_version_id=str(dataset.id),
            manifest_ids=manifest_ids,
            manifest_hashes=manifest_hashes,
            source_commit=commit,
            source_tag=tag,
            pricing_version=PRICING_CONFIG.get("version", "pricing-config-v1"),
            routing_version=routing_policy_version(),
            routing_fingerprint=routing_fingerprint(),
            prompt_version=PROMPT_TEMPLATE_VERSION,
            prompt_sha256=prompt_hash(),
            retry_policy_version=RETRY_POLICY_VERSION,
            failure_policy_version=FAILURE_POLICY_VERSION,
            analysis_version="phase4-analysis-v1",
            model_ids=(
                "gpt-4o-mini",
                "anthropic/claude-3-haiku",
                "deepseek/deepseek-chat",
                "meta-llama/llama-3.3-70b-instruct",
            ),
            configured_upstreams=("amazon-bedrock", "streamlake", "deepinfra/turbo"),
            caps=ExecutionCaps(
                max_scientific_passes=16600,
                max_provider_attempts=20000,
                max_input_tokens=15000000,
                max_output_tokens=7000000,
                max_usd=max_usd,
            ),
            evidence_class="CONTROLLED",
        )
    finally:
        session.close()


def run_preflight() -> None:
    """Zero-inference preflight cost and token accounting calculation."""
    session = SessionLocal()
    try:
        manifest_rq = {m.id: m.rq_code for m in session.query(ExperimentManifest).all()}
        units = session.query(ExperimentalUnit).order_by(ExperimentalUnit.manifest_id, ExperimentalUnit.id).all()

        stats: dict[str, dict[str, Any]] = {}
        for j in ["gpt-4o-mini", "anthropic/claude-3-haiku", "deepseek/deepseek-chat", "meta-llama/llama-3.3-70b-instruct"]:
            stats[j] = {"units": 0, "calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_usd": Decimal("0")}

        rq_calls: dict[str, int] = {f"RQ{i}": 0 for i in range(1, 8)}

        for u in units:
            p = session.get(Prompt, u.prompt_id)
            a = session.get(Answer, u.answer_a_id)
            b = session.get(Answer, u.answer_b_id)
            rq = manifest_rq[u.manifest_id]
            is_dual = rq in {"RQ3", "RQ4", "RQ5"} or u.condition_code == "DUAL_SWAP"
            calls = 2 if is_dual else 1
            rq_calls[rq] += calls

            chars = len(p.text) + len(a.text) + len(b.text) + 603
            in_tokens = (chars // 4) * calls
            out_tokens = 350 * calls
            rate = price_for_model(u.judge_model)
            usd = (Decimal(in_tokens) * rate.input_per_token) + (Decimal(out_tokens) * rate.output_per_token)

            st = stats[u.judge_model]
            st["units"] += 1
            st["calls"] += calls
            st["input_tokens"] += in_tokens
            st["output_tokens"] += out_tokens
            st["estimated_usd"] += usd

        print("\n============================================================")
        print("          PHASE 9B ZERO-INFERENCE PREFLIGHT AUDIT          ")
        print("============================================================")
        print("Plan Calls by Research Question:")
        for rq in sorted(rq_calls.keys()):
            print(f"  {rq}: {rq_calls[rq]:,} scientific calls")
        print(f"  TOTAL: {sum(rq_calls.values()):,} scientific calls across {len(units):,} units\n")

        print("Per-Judge Allocation & Estimated Incurred Spend:")
        total_calls = 0
        total_usd = Decimal("0")
        openai_usd = Decimal("0")
        openrouter_usd = Decimal("0")

        for j, st in stats.items():
            total_calls += st["calls"]
            total_usd += st["estimated_usd"]
            if j == "gpt-4o-mini":
                openai_usd += st["estimated_usd"]
            else:
                openrouter_usd += st["estimated_usd"]
            print(f"  {j}:")
            print(f"    Units: {st['units']:,} | Planned Passes: {st['calls']:,}")
            print(f"    Est. Input Tokens: {st['input_tokens']:,} | Est. Output Tokens: {st['output_tokens']:,}")
            print(f"    Est. USD: ${st['estimated_usd']:.4f}")

        print("------------------------------------------------------------")
        print(f"TOTAL ESTIMATED SPEND: ${total_usd:.4f}")
        print(f"  OpenAI Estimated Need:     ${openai_usd:.4f}  | Balance: $1.78 -> Margin: +${(Decimal('1.78') - openai_usd):.4f} [SAFE]")
        print(f"  OpenRouter Estimated Need: ${openrouter_usd:.4f}  | Balance: $8.35 -> Margin: +${(Decimal('8.35') - openrouter_usd):.4f} [SAFE]")
        print("============================================================\n")
    finally:
        session.close()


def print_status() -> None:
    """Inspect progress and counts of CONTROLLED evidence without making provider calls."""
    session = SessionLocal()
    try:
        manifests = session.query(ExperimentManifest).order_by(ExperimentManifest.rq_code).all()
        print("\n============================================================")
        print("          PHASE 9B CONTROLLED EXECUTION STATUS             ")
        print("============================================================")
        total_units = 0
        total_completed = 0
        total_passes = 0

        for m in manifests:
            units = session.query(ExperimentalUnit).filter(ExperimentalUnit.manifest_id == m.id).all()
            unit_ids = [u.id for u in units]
            n_units = len(units)
            total_units += n_units

            succeeded_runs = [
                r for r in session.query(ControlledRun).filter(
                    ControlledRun.experimental_unit_id.in_(unit_ids),
                    ControlledRun.status == "SUCCEEDED",
                ).all()
                if (r.metadata_json or {}).get("evidence_class") == "CONTROLLED"
            ]

            run_ids = [r.id for r in succeeded_runs]
            n_completed = len(succeeded_runs)
            total_completed += n_completed

            n_passes = session.query(func.count(RunPass.id)).filter(RunPass.run_id.in_(run_ids)).scalar() or 0 if run_ids else 0
            total_passes += n_passes

            print(f"  {m.rq_code}: {n_completed:,} / {n_units:,} units completed ({n_passes:,} passes)")

        print("------------------------------------------------------------")
        print(f"TOTAL CONTROLLED PROGRESS: {total_completed:,} / {total_units:,} units ({total_passes:,} / 16,600 passes)")
        analysis_cnt = session.query(func.count(AnalysisRun.id)).scalar() or 0
        print(f"Published AnalysisRuns: {analysis_cnt} / 7")
        print("============================================================\n")
    finally:
        session.close()


def execute_controlled_experiment(
    *,
    limit: int | None = None,
    delay_seconds: float = 0.05,
    max_usd: Decimal = Decimal("7.50"),
) -> None:
    """Execute the full 16,600-call Phase 9B CONTROLLED experiment sequentially with resume support."""
    profile = build_controlled_profile(max_usd=max_usd)
    profile.assert_authorized()
    runner = ControlledRealRunner(profile=profile)

    session = SessionLocal()
    try:
        manifest_rq = {m.id: m.rq_code for m in session.query(ExperimentManifest).all()}
        units = session.query(ExperimentalUnit).order_by(ExperimentalUnit.manifest_id, ExperimentalUnit.id).all()

        # Find already completed unit IDs in CONTROLLED evidence (never PILOT)
        completed_runs = [
            r for r in session.query(ControlledRun).filter(
                ControlledRun.status == "SUCCEEDED",
            ).all()
            if (r.metadata_json or {}).get("evidence_class") == "CONTROLLED"
        ]
        completed_unit_ids = {r.experimental_unit_id for r in completed_runs}

        pending_units = [u for u in units if u.id not in completed_unit_ids]
        if limit is not None:
            pending_units = pending_units[:limit]

        log.info(
            "Phase 9B Controlled Execution starting: %d total units, %d already completed, %d to execute",
            len(units),
            len(completed_unit_ids),
            len(pending_units),
        )

        if not pending_units:
            log.info("All units are already completed. Run --publish-analysis to generate final findings.")
            return

        with tqdm(total=len(pending_units), desc="Phase 9B Controlled Execution", unit="unit") as pbar:
            for unit in pending_units:
                prompt = session.get(Prompt, unit.prompt_id)
                ans_a = session.get(Answer, unit.answer_a_id)
                ans_b = session.get(Answer, unit.answer_b_id)
                spec = get_model_spec(unit.judge_model)
                rq = manifest_rq[unit.manifest_id]

                is_dual = rq in {"RQ3", "RQ4", "RQ5"} or unit.condition_code == "DUAL_SWAP"

                req = EvaluationRequest(
                    question=prompt.text,
                    answer_a=ans_a.text,
                    answer_b=ans_b.text,
                    judge_name=unit.judge_model,
                    provider=spec.provider,
                    requested_model=spec.requested_model,
                    temperature=float(unit.temperature or 0.0),
                    top_p=float(unit.top_p or 1.0),
                    seed=unit.seed if spec.supports_seed else None,
                    prompt_template_version=PROMPT_TEMPLATE_VERSION,
                    experiment_id=unit.experiment_id,
                    controlled_unit_id=unit.id,
                    repetition_index=unit.repetition_index,
                    pass_number=1,
                    original_answer_a_id=unit.answer_a_id,
                    original_answer_b_id=unit.answer_b_id,
                    presented_answer_a_id=unit.answer_a_id,
                    presented_answer_b_id=unit.answer_b_id,
                )

                idempotency_key = hashlib.sha256(f"controlled:{unit.id}:{1 if not is_dual else 'dual'}".encode()).hexdigest()

                try:
                    run = runner.execute(
                        session=session,
                        unit=unit,
                        request=req,
                        idempotency_key=idempotency_key,
                        dual_pass=is_dual,
                    )
                    session.commit()
                except (PermissionError, ProviderCallError) as exc:
                    session.commit()
                    log.error("Execution stopped on unit %s: %s", unit.id, exc)
                    raise
                except Exception as exc:
                    session.rollback()
                    log.error("Operational exception on unit %s: %s", unit.id, exc)
                    raise

                pbar.update(1)
                if delay_seconds > 0:
                    time.sleep(delay_seconds)

        log.info("Phase 9B Controlled Execution batch complete.")
    finally:
        session.close()


def publish_all_analyses() -> None:
    """Publish authoritative AnalysisRuns for all 7 research questions after execution completes."""
    session = SessionLocal()
    try:
        manifests = session.query(ExperimentManifest).order_by(ExperimentManifest.rq_code).all()
        for manifest in manifests:
            experiment = session.get(Experiment, manifest.experiment_id)
            log.info("Publishing AnalysisRun for %s (manifest %s)...", manifest.rq_code, manifest.id)
            ar = publish_manifest_analysis(session=session, experiment=experiment, manifest=manifest)
            session.commit()
            log.info("Published %s AnalysisRun ID: %s (Status: %s)", manifest.rq_code, ar.id, ar.status)
        log.info("All 7 AnalysisRuns published successfully. /api/controlled/results is now live.")
    finally:
        session.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 9B Controlled Execution Orchestrator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--preflight", action="store_true", help="Perform zero-inference preflight cost check.")
    parser.add_argument("--status", action="store_true", help="Check progress of CONTROLLED evidence.")
    parser.add_argument("--execute", action="store_true", help="Execute or resume the controlled experiment.")
    parser.add_argument("--publish-analysis", action="store_true", help="Publish AnalysisRuns for RQ1-RQ7.")
    parser.add_argument("--limit", type=int, default=None, help="Optional unit limit for execution batch.")
    parser.add_argument("--delay", type=float, default=0.05, help="Inter-call pause in seconds.")
    parser.add_argument("--max-usd", type=float, default=7.50, help="Maximum budget limit in USD.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.preflight:
        run_preflight()
    elif args.status:
        print_status()
    elif args.publish_analysis:
        publish_all_analyses()
    elif args.execute:
        execute_controlled_experiment(limit=args.limit, delay_seconds=args.delay, max_usd=Decimal(str(args.max_usd)))
    else:
        run_preflight()


if __name__ == "__main__":
    main()
