"""Authoritative mock-only rehearsal runner for frozen controlled protocols.

Real provider execution is intentionally impossible in this module.  It plans,
validates, persists mock evidence in a caller-supplied isolated database,
analyzes it, serializes it, and can export it to an explicitly supplied dry-run
location.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from controlled_analysis_adapter import rq1_from_run, rq2_from_run, rq3_from_run, resume_state
from controlled_evaluation import ControlledEvaluationEngine, ControlledExecutionService, EvaluationRequest
from controlled_prompt import PROMPT_TEMPLATE_VERSION, prompt_hash
from controlled_models import ControlledRun, CounterfactualVariant, Experiment, ExperimentalCondition, ExperimentManifest, ExperimentalUnit
from controlled_persistence import ControlledPersistence
from mock_provider import DeterministicMockProvider, MockScenario
from model_registry import MODEL_REGISTRY, Provider
from models import Answer, Prompt
from phase3_planning import SOURCE_FAMILIES, PairRecord, PlannedUnit, call_plan, generate_units, manifest, validate_units
from phase3_protocols import PLANNED_BASE_UNIT_LIMIT, PROTOCOLS
from phase3_transforms import make_format_variant, make_verbosity_variant, validate_format_variant, validate_verbosity_variant
from phase4_metrics import RQ6Unit, RQ7Observation, VariantPair, analyze_rq1, analyze_rq2, analyze_rq3, analyze_rq4, analyze_rq5, analyze_rq6, analyze_rq7


MOCK_EVIDENCE_CLASS = "DRY_RUN_MOCK"
OUTPUT_TOKEN_BUDGET = 350


@dataclass(frozen=True)
class ExecutionProfile:
    profile_name: str = "phase6-mock-rehearsal-v1"
    base_unit_limit: int = PLANNED_BASE_UNIT_LIMIT
    analysis_seed: int = 20260818
    bootstrap_iterations: int = 200
    mock_only: bool = True


@dataclass(frozen=True)
class PlanSummary:
    rq_code: str
    protocol_version: str
    manifest_sha256: str
    planned_units: int
    planned_calls: int
    judges: tuple[str, ...]
    conditions: tuple[str, ...]
    repetitions: int
    pass_count: int


def _scenario(unit_id: str, pass_count: int) -> list[MockScenario]:
    """Stable failure injection, keyed only by immutable planned unit identity."""
    choices = (MockScenario.ANSWER_A, MockScenario.ANSWER_B, MockScenario.TIE, MockScenario.UNKNOWN, MockScenario.INVALID_JSON, MockScenario.PROVIDER_ERROR, MockScenario.TIMEOUT)
    digest = int(hashlib.sha256(unit_id.encode()).hexdigest()[:8], 16)
    return [choices[(digest + index) % len(choices)] for index in range(pass_count)]


class ControlledRunner:
    def __init__(self, profile: ExecutionProfile = ExecutionProfile()) -> None:
        if not profile.mock_only: raise ValueError("Phase 6 runner accepts MOCK_ONLY profiles exclusively")
        self.profile = profile

    def plan(self, pairs: Iterable[PairRecord], *, snapshot_id: str) -> tuple[dict[str, list[PlannedUnit]], dict[str, PlanSummary]]:
        rows = list(pairs); plans = {rq: generate_units(rows, rq, limit=self.profile.base_unit_limit, snapshot_id=snapshot_id) for rq in PROTOCOLS}
        summaries = {rq: PlanSummary(rq, PROTOCOLS[rq].protocol_version, manifest(rq, units, snapshot_id)["manifest_sha256"], len(units), sum(u.calls for u in units), PROTOCOLS[rq].judges, PROTOCOLS[rq].conditions, PROTOCOLS[rq].repetitions, PROTOCOLS[rq].pass_count) for rq, units in plans.items()}
        return plans, summaries

    def validate(self, plans: dict[str, list[PlannedUnit]]) -> list[str]:
        errors: list[str] = []; manifest_hashes: list[str] = []; ids: list[str] = []
        for rq, units in plans.items():
            errors.extend(f"{rq}:{error}" for error in validate_units(units)); ids.extend(u.unit_id for u in units)
            manifest_hashes.append(manifest(rq, units, "validation-snapshot")["manifest_sha256"])
            for unit in units:
                if unit.judge_name not in MODEL_REGISTRY: errors.append(f"{rq}:unsupported_judge:{unit.judge_name}")
                if not unit.requested_model or not unit.provider: errors.append(f"{rq}:missing_model_provider:{unit.unit_id}")
        if len(ids) != len(set(ids)): errors.append("duplicate_planned_unit_id")
        if len(manifest_hashes) != len(set(manifest_hashes)): errors.append("duplicate_manifest_hash")
        return errors

    def dry_run(self, session: Session, pairs: Iterable[PairRecord], *, snapshot_id: str) -> dict[str, object]:
        plans, summaries = self.plan(pairs, snapshot_id=snapshot_id); errors = self.validate(plans)
        if errors: raise ValueError(f"Invalid dry-run plan: {errors}")
        source = {pair.pair_key: pair for pair in pairs}; repo = ControlledPersistence(session)
        dataset = repo.get_or_create_dataset_version(source_name="phase6-real-frozen-input", version=snapshot_id, source_checksum=hashlib.sha256(snapshot_id.encode()).hexdigest(), import_status="SUCCEEDED", notes="MOCK / DRY-RUN — NOT SCIENTIFIC EVIDENCE")
        local: dict[str, tuple[Prompt, Answer, Answer]] = {}; variants: dict[tuple[str, str], Answer] = {}; runs: dict[str, list[tuple[ControlledRun, ExperimentalUnit, PairRecord, PlannedUnit]]] = defaultdict(list)
        for rq, units in plans.items():
            protocol = PROTOCOLS[rq]; experiment_name = f"dry-run-{rq}-{snapshot_id}"
            experiment = session.scalar(select(Experiment).where(Experiment.experiment_name == experiment_name))
            if experiment is None: experiment = repo.create_experiment(dataset_version=dataset, experiment_name=experiment_name, research_question=protocol.research_question, hypothesis=protocol.hypothesis, mitigation_strategy="MOCK_ONLY", analysis_version="phase4-analysis-v1", metadata_json={"evidence_class": MOCK_EVIDENCE_CLASS})
            manifest_row = session.scalar(select(ExperimentManifest).where(ExperimentManifest.experiment_id == experiment.id, ExperimentManifest.manifest_sha256 == summaries[rq].manifest_sha256))
            if manifest_row is None: manifest_row = repo.create_manifest(experiment=experiment, rq_code=rq, protocol_version=protocol.protocol_version, analysis_version="phase4-analysis-v1", dataset_snapshot_id=snapshot_id, dataset_checksum=hashlib.sha256(snapshot_id.encode()).hexdigest(), manifest_sha256=summaries[rq].manifest_sha256, manifest_json={"evidence_class": MOCK_EVIDENCE_CLASS, "provider_execution": "DISABLED"})
            conditions = {}
            for planned in units:
                pair = source[planned.base_pair_key]
                if pair.pair_key not in local:
                    prompt_text = f"[dry-run source {pair.prompt_id}]"
                    prompt = session.scalar(select(Prompt).where(Prompt.text == prompt_text, Prompt.category == pair.category))
                    if prompt is None:
                        prompt = Prompt(text=prompt_text, category=pair.category); session.add(prompt); session.flush()
                    a = session.scalar(select(Answer).where(Answer.prompt_id == prompt.id, Answer.model_name == pair.answer_a_model, Answer.text == pair.answer_a_text)); b = session.scalar(select(Answer).where(Answer.prompt_id == prompt.id, Answer.model_name == pair.answer_b_model, Answer.text == pair.answer_b_text))
                    if a is None: a = Answer(prompt_id=prompt.id, model_name=pair.answer_a_model, text=pair.answer_a_text, word_count=len(pair.answer_a_text.split())); session.add(a)
                    if b is None: b = Answer(prompt_id=prompt.id, model_name=pair.answer_b_model, text=pair.answer_b_text, word_count=len(pair.answer_b_text.split())); session.add(b)
                    session.flush(); local[pair.pair_key] = (prompt, a, b)
                prompt, a, b = local[pair.pair_key]
                if planned.condition not in conditions:
                    conditions[planned.condition] = session.scalar(select(ExperimentalCondition).where(ExperimentalCondition.experiment_id == experiment.id, ExperimentalCondition.condition_code == planned.condition))
                    if conditions[planned.condition] is None: conditions[planned.condition] = repo.create_condition(experiment=experiment, condition_code=planned.condition, label=planned.condition, condition_json={"mock_only": True, "prompt_hash": prompt_hash()}, protocol_version=protocol.protocol_version, prompt_template_version=PROMPT_TEMPLATE_VERSION)
                presentation_a, presentation_b, variant_checksum = a, b, planned.variant_checksum
                if rq in {"RQ4", "RQ5"}:
                    key = (rq, pair.pair_key)
                    if key not in variants:
                        variant_text = make_verbosity_variant(a.text) if rq == "RQ4" else make_format_variant(a.text)
                        validation = validate_verbosity_variant(a.id, a.text, variant_text) if rq == "RQ4" else validate_format_variant(a.id, a.text, variant_text)
                        if not validation.valid: raise ValueError(f"Invalid planned {rq} variant")
                        existing_variant = session.scalar(select(CounterfactualVariant).where(CounterfactualVariant.original_answer_id == a.id, CounterfactualVariant.condition_code == planned.condition, CounterfactualVariant.transformation_version == "phase3-controlled-v1", CounterfactualVariant.variant_checksum == validation.variant_checksum))
                        if existing_variant is not None and existing_variant.variant_answer_id is not None: variant = session.get(Answer, existing_variant.variant_answer_id)
                        else:
                            variant = Answer(prompt_id=prompt.id, model_name="dry-run-variant", text=variant_text, word_count=len(variant_text.split())); session.add(variant); session.flush()
                            session.add(CounterfactualVariant(original_answer_id=a.id, variant_answer_id=variant.id, condition_code=planned.condition, transformation_method=validation.variant_type, transformation_version="phase3-controlled-v1", original_checksum=validation.source_checksum, variant_checksum=validation.variant_checksum, original_word_count=validation.source_word_count, variant_word_count=validation.variant_word_count, original_token_estimate=validation.source_word_count, variant_token_estimate=validation.variant_word_count, validation_status=validation.status, validation_details={"evidence_class": MOCK_EVIDENCE_CLASS}))
                        variants[key] = variant
                    presentation_b = variants[key]
                seed = 42 if MODEL_REGISTRY[planned.judge_name].supports_seed else None
                if rq == "RQ6":
                    self_family = {"gpt-4o-mini": "OPENAI", "anthropic/claude-3-haiku": "ANTHROPIC", "meta-llama/llama-3.3-70b-instruct": "META_LLAMA"}[planned.judge_name]
                    a_is_self = SOURCE_FAMILIES.get(pair.answer_a_model) == self_family
                    if (planned.presentation_order == "SELF_A") != a_is_self:
                        presentation_a, presentation_b = presentation_b, presentation_a
                unit = repo.register_unit(experiment=experiment, manifest=manifest_row, condition=conditions[planned.condition], prompt_id=prompt.id, answer_a_id=a.id, answer_b_id=b.id, prompt_category=pair.category, judge_model=planned.judge_name, provider=planned.provider, provider_model=planned.requested_model, prompt_template_version=PROMPT_TEMPLATE_VERSION, presentation_order=planned.presentation_order, repetition_index=planned.repetition_index, randomization_block="dry-run", data_split="dry-run", inclusion_status="INCLUDED", temperature=Decimal(str(planned.temperature)), top_p=Decimal("1.0"), seed=seed, answer_a_author_id=pair.answer_a_model, answer_b_author_id=pair.answer_b_model, human_label=pair.human_label, variant_checksum=variant_checksum)
                req = EvaluationRequest(question=prompt.text, answer_a=presentation_a.text, answer_b=presentation_b.text, judge_name=planned.judge_name, provider=Provider(planned.provider), requested_model=planned.requested_model, temperature=planned.temperature, top_p=1.0, seed=seed, prompt_template_version=PROMPT_TEMPLATE_VERSION, experiment_id=experiment.id, controlled_unit_id=unit.id, repetition_index=unit.repetition_index, pass_number=1, original_answer_a_id=unit.answer_a_id, original_answer_b_id=unit.answer_b_id, presented_answer_a_id=presentation_a.id, presented_answer_b_id=presentation_b.id)
                executor = ControlledExecutionService(repo, ControlledEvaluationEngine(DeterministicMockProvider(_scenario(planned.unit_id, planned.calls), effective_model=f"mock/{planned.judge_name}")))
                run = executor.execute_dual(unit=unit, first_request=req, idempotency_key=planned.unit_id) if planned.calls == 2 else executor.execute_single(unit=unit, request=req, idempotency_key=planned.unit_id)
                runs[rq].append((run, unit, pair, planned))
        return {"evidence_class": MOCK_EVIDENCE_CLASS, "plans": summaries, "runs": runs, "status": self.status(runs)}

    @staticmethod
    def status(runs: dict[str, list[tuple[ControlledRun, ExperimentalUnit, PairRecord, PlannedUnit]]]) -> dict[str, dict[str, int]]:
        report = {}
        for rq, rows in runs.items():
            flat = [r[0] for r in rows]; states = resume_state(flat); passes = [p for run in flat for p in run.passes]
            report[rq] = {"planned_units": len(rows), "runs": len(flat), "passes": len(passes), "completed": len(states.completed), "pending": len(states.pending), "retryable": len(states.retryable), "non_retryable": len(states.non_retryable), "failed": sum(r.status == "FAILED" for r in flat)}
        return report

    def analyze(self, rehearsal: dict[str, object]) -> dict[str, object]:
        runs = rehearsal["runs"]; seed = self.profile.analysis_seed; n = self.profile.bootstrap_iterations
        rq1 = [rq1_from_run(run, unit) for run, unit, _, _ in runs["RQ1"]]
        rq2 = [rq2_from_run(run, unit, group_key=f"{pair.pair_key}|{planned.judge_name}|{planned.condition}|{planned.temperature}", seed_policy="provider-recorded") for run, unit, pair, planned in runs["RQ2"]]
        rq3 = [rq3_from_run(run, unit) for run, unit, _, _ in runs["RQ3"]]
        def variant_rows(rq: str):
            out=[]
            for run, unit, _, _ in runs[rq]:
                outcome = run.passes[0].raw_verdict if run.passes else None
                mapped = "VARIANT" if outcome == "ANSWER_B" else "ORIGINAL" if outcome == "ANSWER_A" else "TIE" if outcome == "TIE" else None
                out.append(VariantPair("CONTROLLED", str(unit.id), rq, run.judge_name, unit.condition_code, True, mapped, unit.presentation_order))
            return out
        rq6=[]
        for run, unit, pair, planned in runs["RQ6"]:
            self_family = {"gpt-4o-mini": "OPENAI", "anthropic/claude-3-haiku": "ANTHROPIC", "meta-llama/llama-3.3-70b-instruct": "META_LLAMA"}.get(run.judge_name)
            fam = {"gpt-4": "OPENAI", "gpt-3.5-turbo": "OPENAI", "claude-v1": "ANTHROPIC", "llama-13b": "META_LLAMA"}; winner = run.final_winner_answer_id
            winner_family = fam.get(pair.answer_a_model if winner == unit.answer_a_id else pair.answer_b_model if winner == unit.answer_b_id else "")
            rq6.append(RQ6Unit("CONTROLLED", str(unit.id), "RQ6", run.judge_name, unit.condition_code, winner_family is not None, "SELF" if winner_family == self_family else "OTHER" if winner_family else "TIE" if run.final_result_type == "TIE" else None, "A" if planned.presentation_order == "SELF_A" else "B"))
        grouped=defaultdict(dict)
        for run, unit, pair, planned in runs["RQ7"]:
            def mapped(record):
                if record is None: return None
                if record.raw_verdict == "TIE": return "TIE"
                if record.raw_verdict == "UNKNOWN": return "UNKNOWN"
                if record.winner_answer_id == unit.answer_a_id: return "ANSWER_A"
                if record.winner_answer_id == unit.answer_b_id: return "ANSWER_B"
                return "INVALID_RESPONSE"
            if planned.condition == "BASELINE_STANDARD":
                grouped[(pair.pair_key, run.judge_name)]["baseline"] = mapped(run.passes[0] if run.passes else None)
                grouped[(pair.pair_key, run.judge_name)]["human"] = unit.human_label
            else:
                grouped[(pair.pair_key, run.judge_name)]["dual_ab"] = mapped(next((p for p in run.passes if p.pass_number == 1), None))
                grouped[(pair.pair_key, run.judge_name)]["dual_ba"] = mapped(next((p for p in run.passes if p.pass_number == 2), None))
                grouped[(pair.pair_key, run.judge_name)]["human"] = unit.human_label
        rq7=[RQ7Observation("CONTROLLED", f"{key[0]}:{key[1]}", "RQ7", key[1], "MATCHED", key[0], value.get("human"), value.get("baseline"), value.get("dual_ab"), value.get("dual_ba")) for key,value in grouped.items()]
        result={"RQ1": analyze_rq1(rq1, seed=seed, iterations=n), "RQ2": analyze_rq2(rq2, seed=seed, iterations=n), "RQ3": analyze_rq3(rq3, seed=seed, iterations=n), "RQ4": analyze_rq4(variant_rows("RQ4"), seed=seed, iterations=n), "RQ5": analyze_rq5(variant_rows("RQ5"), seed=seed, iterations=n), "RQ6": analyze_rq6(rq6, seed=seed, iterations=n), "RQ7": analyze_rq7(rq7)}
        serialized: dict[str, dict[str, dict[str, object]]] = {}
        for rq, metrics in result.items():
            serialized[rq] = {}
            for name, metric in metrics.items():
                row = metric.serialize()
                # This is the future controlled-result API shape.  Keep the
                # authoritative MetricResult names too, but provide stable
                # consumer aliases rather than asking a UI to infer a zero
                # from an absent/NOT_ESTIMABLE metric.
                serialized[rq][name] = {
                    **row,
                    "rq": rq,
                    "metric": row["metric_name"],
                    "ties": row["tie_count"],
                    "unknowns": row["unknown_count"],
                    "failures": row["failure_count"],
                    "excluded": row["excluded_count"],
                    "analysis_version": row["metric_version"],
                    "evidence_class": MOCK_EVIDENCE_CLASS,
                }
        return serialized

    def preflight(self, pairs: Iterable[PairRecord], *, snapshot_id: str) -> dict[str, dict[str, int | str]]:
        rows={pair.pair_key: pair for pair in pairs}; plans,_=self.plan(rows.values(), snapshot_id=snapshot_id); total=defaultdict(lambda: {"planned_calls":0,"estimated_input_tokens":0,"estimated_output_tokens":0,"pricing":"PRICING VERIFICATION REQUIRED"})
        for units in plans.values():
            for unit in units:
                pair=rows[unit.base_pair_key]; chars=len(pair.answer_a_text)+len(pair.answer_b_text)+80
                total[unit.judge_name]["planned_calls"] += unit.calls; total[unit.judge_name]["estimated_input_tokens"] += ((chars+3)//4)*unit.calls; total[unit.judge_name]["estimated_output_tokens"] += OUTPUT_TOKEN_BUDGET*unit.calls
        return dict(total)

    @staticmethod
    def export(analysis: dict[str, object], path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps({"evidence_class": MOCK_EVIDENCE_CLASS, "analysis": analysis}, indent=2, sort_keys=True), encoding="utf-8"); return path

    @staticmethod
    def execute_real(*_args, **_kwargs) -> None:
        raise PermissionError("Real provider execution is disabled. A future authorized profile and budget gate are required.")

    @staticmethod
    def enforce_budget(*, calls: int, tokens: int, max_calls: int, max_tokens: int, max_usd_budget: float | None = None) -> None:
        if calls > max_calls or tokens > max_tokens: raise ValueError("Budget guard stopped execution before any provider call")
        if max_usd_budget is not None: raise ValueError("USD enforcement requires verified frozen pricing; execution remains disabled")
