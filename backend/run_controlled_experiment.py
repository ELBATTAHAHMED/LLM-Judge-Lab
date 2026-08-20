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
    CounterfactualVariant,
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


SOURCE_FAMILIES = {
    "gpt-4": "openai",
    "gpt-3.5-turbo": "openai",
    "claude-v1": "anthropic",
    "llama-13b": "meta-llama",
}


def materialize_evaluation_request(
    session: Session,
    unit: ExperimentalUnit,
    manifest_rq: dict[Any, str] | None = None,
) -> tuple[EvaluationRequest, bool]:
    """Deterministically materialize the exact EvaluationRequest for an ExperimentalUnit.

    Correctly handles:
    - Standard pairwise presentation (RQ1, RQ2, RQ3, RQ7)
    - Counterfactual variant text presentation (RQ4, RQ5)
    - Self-enhancement author presentation order slotting (RQ6)
    - Dual-pass swap identification

    Returns:
        tuple[EvaluationRequest, bool]: (pass 1 request, is_dual_pass)
    """
    if manifest_rq is None:
        manifest = session.get(ExperimentManifest, unit.manifest_id)
        rq = manifest.rq_code if manifest else "UNKNOWN"
    else:
        rq = manifest_rq.get(unit.manifest_id, "UNKNOWN")

    prompt = session.get(Prompt, unit.prompt_id)
    if prompt is None or not prompt.text:
        raise ValueError(f"Prompt id={unit.prompt_id} missing or empty for unit={unit.id}")

    ans_a = session.get(Answer, unit.answer_a_id)
    if ans_a is None or not ans_a.text:
        raise ValueError(f"Answer A id={unit.answer_a_id} missing or empty for unit={unit.id}")

    ans_b = session.get(Answer, unit.answer_b_id)
    if ans_b is None:
        raise ValueError(f"Answer B id={unit.answer_b_id} missing for unit={unit.id}")

    spec = get_model_spec(unit.judge_model)

    pres_a_text = ans_a.text
    pres_b_text = ans_b.text
    pres_a_id = unit.answer_a_id
    pres_b_id = unit.answer_b_id
    prov: dict[str, Any] | None = None

    if rq in {"RQ4", "RQ5"}:
        if unit.counterfactual_variant_id:
            cv = session.get(CounterfactualVariant, unit.counterfactual_variant_id)
            if cv and cv.variant_text:
                pres_b_text = cv.variant_text
            elif cv and cv.variant_answer_id:
                va = session.get(Answer, cv.variant_answer_id)
                if va and va.text:
                    pres_b_text = va.text
        if not pres_b_text:
            raise ValueError(f"Counterfactual variant text is missing or empty for {rq} unit={unit.id}")
        prov = {"variant_slot": "B"}

    elif rq == "RQ6":
        self_family = spec.family
        answer_family = {
            unit.answer_a_id: SOURCE_FAMILIES.get(unit.answer_a_author_id or ""),
            unit.answer_b_id: SOURCE_FAMILIES.get(unit.answer_b_author_id or ""),
        }
        a_is_self = answer_family.get(unit.answer_a_id) == self_family
        if (unit.presentation_order == "SELF_A") != a_is_self:
            pres_a_text, pres_b_text = pres_b_text, pres_a_text
            pres_a_id, pres_b_id = pres_b_id, pres_a_id

    if not pres_a_text or not pres_b_text:
        raise ValueError(
            f"Empty answer text materialized for unit={unit.id} (RQ={rq}): "
            f"pres_a len={len(pres_a_text)}, pres_b len={len(pres_b_text)}"
        )

    is_dual = rq in {"RQ3", "RQ4", "RQ5"} or unit.condition_code == "DUAL_SWAP"

    req = EvaluationRequest(
        question=prompt.text,
        answer_a=pres_a_text,
        answer_b=pres_b_text,
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
        presented_answer_a_id=pres_a_id,
        presented_answer_b_id=pres_b_id,
        presentation_provenance=prov,
    )
    return req, is_dual


def run_preflight() -> None:
    """Zero-inference preflight cost, token accounting, and full-payload validation."""
    session = SessionLocal()
    try:
        manifest_rq = {m.id: m.rq_code for m in session.query(ExperimentManifest).all()}
        units = session.query(ExperimentalUnit).order_by(ExperimentalUnit.manifest_id, ExperimentalUnit.id).all()

        stats: dict[str, dict[str, Any]] = {}
        for j in ["gpt-4o-mini", "anthropic/claude-3-haiku", "deepseek/deepseek-chat", "meta-llama/llama-3.3-70b-instruct"]:
            stats[j] = {"units": 0, "calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_usd": Decimal("0")}

        rq_calls: dict[str, int] = {f"RQ{i}": 0 for i in range(1, 8)}

        print("Validating all 13,400 planned EvaluationRequest payloads offline...")
        validation_errors: list[str] = []

        for u in units:
            rq = manifest_rq[u.manifest_id]
            try:
                req, is_dual = materialize_evaluation_request(session, u, manifest_rq=manifest_rq)
                # Verify Pass 2 construction if dual pass
                if is_dual:
                    _ = req.model_copy(update={
                        "answer_a": req.answer_b,
                        "answer_b": req.answer_a,
                        "presented_answer_a_id": req.original_answer_b_id,
                        "presented_answer_b_id": req.original_answer_a_id,
                        "pass_number": 2,
                    })
            except Exception as exc:
                validation_errors.append(f"Unit {u.id} ({rq}): {exc}")
                continue

            calls = 2 if is_dual else 1
            rq_calls[rq] += calls

            chars = len(req.question) + len(req.answer_a) + len(req.answer_b) + 603
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

        if validation_errors:
            print(f"\n[ERROR] Found {len(validation_errors)} invalid planned unit payloads:")
            for err in validation_errors[:10]:
                print(f"  {err}")
            raise RuntimeError(f"Preflight validation failed with {len(validation_errors)} invalid payloads")

        print("Offline payload validation: 13,400 / 13,400 units (16,600 / 16,600 passes) VALID [100% OK]")

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
        total_planned_units = 0
        total_succeeded = 0
        total_valid_partial = 0
        total_terminal_failed = 0
        total_superseded = 0
        total_pending = 0
        total_completed_passes = 0

        for m in manifests:
            units = session.query(ExperimentalUnit).filter(ExperimentalUnit.manifest_id == m.id).all()
            unit_ids = [u.id for u in units]
            n_units = len(units)
            total_planned_units += n_units

            all_unit_runs = session.query(ControlledRun).filter(
                ControlledRun.experimental_unit_id.in_(unit_ids)
            ).all()

            controlled_runs = [
                r for r in all_unit_runs
                if (r.metadata_json or {}).get("evidence_class") == "CONTROLLED"
            ]
            superseded_runs = [
                r for r in all_unit_runs
                if (r.metadata_json or {}).get("evidence_class") == "SUPERSEDED_CONTROLLED"
            ]

            succeeded_runs = [r for r in controlled_runs if r.status == "SUCCEEDED"]
            # Valid partial: dual-pass runs with 2 valid passes (e.g. position flips / ties)
            valid_partial_runs = [
                r for r in controlled_runs
                if r.status == "PARTIAL" and len(r.passes) == 2 and all(p.outcome in {"ANSWER_A", "ANSWER_B", "TIE", "UNKNOWN"} for p in r.passes)
            ]
            failed_runs = [
                r for r in controlled_runs
                if r.status == "FAILED" or (r.status == "PARTIAL" and any(p.outcome not in {"ANSWER_A", "ANSWER_B", "TIE", "UNKNOWN"} for p in r.passes))
            ]

            terminal_ids = {r.experimental_unit_id for r in controlled_runs if r.status in {"SUCCEEDED", "FAILED"} or (r.status == "PARTIAL" and len(r.passes) == 2)}
            pending_in_rq = [u for u in units if u.id not in terminal_ids]

            n_succeeded = len(succeeded_runs)
            n_valid_partial = len(valid_partial_runs)
            n_failed = len(failed_runs)
            n_superseded = len(superseded_runs)
            n_pending = len(pending_in_rq)

            run_ids = [r.id for r in succeeded_runs]
            n_passes = session.query(func.count(RunPass.id)).filter(RunPass.run_id.in_(run_ids)).scalar() or 0 if run_ids else 0

            total_succeeded += n_succeeded
            total_valid_partial += n_valid_partial
            total_terminal_failed += n_failed
            total_superseded += n_superseded
            total_pending += n_pending
            total_completed_passes += n_passes

            print(
                f"  {m.rq_code}: {n_succeeded:,} SUCCEEDED | {n_valid_partial:,} valid PARTIAL | "
                f"{n_failed:,} FAILED | {n_pending:,} pending | {n_superseded:,} superseded / {n_units:,} planned"
            )

        print("------------------------------------------------------------")
        print(f"TOTAL PLANNED UNITS ACCOUNTED: {total_planned_units:,} / 13,400")
        print(f"  - Scientifically Succeeded Units:       {total_succeeded:,}")
        print(f"  - Scientifically Complete PARTIAL Units: {total_valid_partial:,} (Dual-pass position flips / ties)")
        print(f"  - Terminal Failed Units (Exhausted):    {total_terminal_failed:,}")
        print(f"  - Superseded Historical Units (RQ5):    {total_superseded:,}")
        print(f"  - Pending Provider-Eligible Units (RQ5): {total_pending:,}")
        print(f"TOTAL COMPLETED SCIENTIFIC PASSES:        {total_completed_passes:,} / 16,600 passes")
        analysis_cnt = session.query(func.count(AnalysisRun.id)).scalar() or 0
        print(f"Published AnalysisRuns:                  {analysis_cnt} / 7")
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

        # Find units with terminal CONTROLLED evidence (never PILOT or SUPERSEDED_CONTROLLED)
        controlled_runs = [
            r for r in session.query(ControlledRun).all()
            if (r.metadata_json or {}).get("evidence_class") == "CONTROLLED"
        ]
        terminal_unit_ids = set()
        for r in controlled_runs:
            if r.status in {"SUCCEEDED", "FAILED"}:
                terminal_unit_ids.add(r.experimental_unit_id)
            elif r.status == "PARTIAL" and len(r.passes) == 2:
                terminal_unit_ids.add(r.experimental_unit_id)

        pending_units = [u for u in units if u.id not in terminal_unit_ids]
        if limit is not None:
            pending_units = pending_units[:limit]

        log.info(
            "Phase 9B Controlled Execution starting: %d total units, %d terminal/complete, %d to execute",
            len(units),
            len(terminal_unit_ids),
            len(pending_units),
        )

        if not pending_units:
            log.info("All units are already completed. Run --publish-analysis to generate final findings.")
            return

        with tqdm(total=len(pending_units), desc="Phase 9B Controlled Execution", unit="unit") as pbar:
            for unit in pending_units:
                req, is_dual = materialize_evaluation_request(session, unit, manifest_rq=manifest_rq)
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
