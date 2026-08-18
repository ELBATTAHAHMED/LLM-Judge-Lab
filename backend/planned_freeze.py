"""Persist the immutable, provider-free controlled execution plan."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from controlled_freeze import FrozenPair, REVERSED_PAIR_POLICY_VERSION, canonical_dataset_checksum
from controlled_persistence import ControlledPersistence
from controlled_models import Experiment, ExperimentalCondition, ExperimentManifest
from controlled_prompt import PROMPT_TEMPLATE_VERSION, prompt_hash
from model_registry import MODEL_REGISTRY
from phase3_planning import PairRecord, database_pairs, generate_units, manifest
from phase3_protocols import PLANNED_BASE_UNIT_LIMIT, PROTOCOLS
from phase3_transforms import make_format_variant, make_verbosity_variant, validate_format_variant, validate_verbosity_variant
from phase4_metrics import ANALYSIS_VERSION


FREEZE_VERSION = "controlled-final-plan-v1"


def _pairs(session: Session) -> list[PairRecord]:
    return database_pairs(session, apply_reference_policy=True)


def persist_final_plan(session: Session, *, limit: int = PLANNED_BASE_UNIT_LIMIT) -> dict[str, Any]:
    pairs = _pairs(session)
    checksum = canonical_dataset_checksum([FrozenPair(p.preference_id, p.prompt_id, p.answer_a_id, p.answer_b_id, p.answer_a_text, p.answer_b_text, p.answer_a_model, p.answer_b_model, p.category, p.human_label) for p in pairs])
    repo = ControlledPersistence(session)
    dataset = repo.get_or_create_dataset_version(source_name="judgelab-canonical-human-reference", version=FREEZE_VERSION, source_checksum=checksum, checksum_algorithm="SHA-256", import_status="SUCCEEDED", imported_prompt_count=107, imported_answer_count=2139, imported_annotation_count=len(pairs), notes=f"PLANNED ONLY; canonicalization={REVERSED_PAIR_POLICY_VERSION}; prompt_hash={prompt_hash()}")
    by_key = {p.pair_key: p for p in pairs}; report: dict[str, Any] = {"dataset_checksum": checksum, "dataset_version_id": str(dataset.id), "rqs": {}}
    for rq, protocol in PROTOCOLS.items():
        name = f"{FREEZE_VERSION}-{rq}-{checksum[:12]}"
        experiment = session.scalar(select(Experiment).where(Experiment.experiment_name == name))
        if experiment is None:
            experiment = repo.create_experiment(dataset_version=dataset, experiment_name=name, research_question=protocol.research_question, hypothesis=protocol.hypothesis, mitigation_strategy="DUAL_SWAP" if rq == "RQ7" else "NONE", analysis_version=ANALYSIS_VERSION, metadata_json={"evidence_class": "PLANNED", "canonicalization_policy": REVERSED_PAIR_POLICY_VERSION, "prompt_hash": prompt_hash()})
        units = generate_units(pairs, rq, limit=limit, snapshot_id=checksum)
        material = manifest(rq, units, checksum)
        man = session.scalar(select(ExperimentManifest).where(ExperimentManifest.experiment_id == experiment.id, ExperimentManifest.manifest_sha256 == material["manifest_sha256"]))
        if man is None:
            man = repo.create_manifest(experiment=experiment, rq_code=rq, protocol_version=protocol.protocol_version, analysis_version=ANALYSIS_VERSION, dataset_snapshot_id=FREEZE_VERSION, dataset_checksum=checksum, manifest_sha256=material["manifest_sha256"], manifest_json={**material, "evidence_class": "PLANNED", "prompt_hash": prompt_hash(), "canonicalization_policy": REVERSED_PAIR_POLICY_VERSION})
        conditions: dict[str, ExperimentalCondition] = {}
        variants: dict[tuple[str, int], Any] = {}
        for planned in units:
            pair = by_key[planned.base_pair_key]
            if planned.condition not in conditions:
                conditions[planned.condition] = session.scalar(select(ExperimentalCondition).where(ExperimentalCondition.experiment_id == experiment.id, ExperimentalCondition.condition_code == planned.condition))
                if conditions[planned.condition] is None:
                    conditions[planned.condition] = repo.create_condition(experiment=experiment, condition_code=planned.condition, label=planned.condition, condition_json={"evidence_class": "PLANNED", "prompt_hash": prompt_hash()}, protocol_version=protocol.protocol_version, prompt_template_version=PROMPT_TEMPLATE_VERSION)
            variant = None
            if rq in {"RQ4", "RQ5"}:
                key = (rq, pair.answer_a_id)
                if key not in variants:
                    text = make_verbosity_variant(pair.answer_a_text) if rq == "RQ4" else make_format_variant(pair.answer_a_text)
                    check = validate_verbosity_variant(pair.answer_a_id, pair.answer_a_text, text) if rq == "RQ4" else validate_format_variant(pair.answer_a_id, pair.answer_a_text, text)
                    if not check.valid:
                        raise ValueError(f"invalid frozen {rq} variant for answer {pair.answer_a_id}")
                    variants[key] = repo.get_or_create_variant(experiment=experiment, original_answer_id=pair.answer_a_id, condition_code=planned.condition, transformation_method=check.variant_type, transformation_version=protocol.protocol_version, original_checksum=check.source_checksum, variant_checksum=check.variant_checksum, variant_text=text, original_word_count=check.source_word_count, variant_word_count=check.variant_word_count, validation_status=check.status, validation_details={"evidence_class": "PLANNED", "base_pair_key": pair.pair_key})
                variant = variants[key]
            spec = MODEL_REGISTRY[planned.judge_name]
            repo.register_unit(experiment=experiment, manifest=man, condition=conditions[planned.condition], prompt_id=pair.prompt_id, answer_a_id=pair.answer_a_id, answer_b_id=pair.answer_b_id, prompt_category=pair.category, judge_model=planned.judge_name, provider=planned.provider, provider_model=planned.requested_model, prompt_template_version=PROMPT_TEMPLATE_VERSION, presentation_order=planned.presentation_order, repetition_index=planned.repetition_index, randomization_block=checksum[:16], data_split="FROZEN_CANONICAL", inclusion_status="INCLUDED", temperature=Decimal(str(planned.temperature)), top_p=Decimal("1"), seed=42 if spec.supports_seed else None, answer_a_author_id=pair.answer_a_model, answer_b_author_id=pair.answer_b_model, human_label=pair.human_label, pairing_key=pair.pair_key, variant_checksum=planned.variant_checksum, counterfactual_variant=variant)
        report["rqs"][rq] = {"manifest_id": str(man.id), "manifest_sha256": man.manifest_sha256, "units": len(units), "calls": sum(u.calls for u in units)}
    return report
