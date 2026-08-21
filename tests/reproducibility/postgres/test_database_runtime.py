"""Disposable PostgreSQL runtime validation; requires PHASE85_POSTGRES_URL."""
from __future__ import annotations

import os
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from controlled_models import ControlledRun, Experiment, ExperimentalUnit
from controlled_persistence import ControlledPersistence
from models import Answer, Prompt


@pytest.fixture()
def postgres_engine():
    url = os.getenv("PHASE85_POSTGRES_URL")
    if not url:
        pytest.skip("PHASE85_POSTGRES_URL not configured")
    engine = create_engine(url)
    try:
        yield engine
    finally:
        engine.dispose()


def test_postgres_execution_hardening_schema_and_round_trip(postgres_engine):
    inspection = inspect(postgres_engine)
    unit_columns = {row["name"]: row for row in inspection.get_columns("experimental_units")}
    run_columns = {row["name"] for row in inspection.get_columns("runs")}
    assert unit_columns["presentation_order"]["type"].length == 32
    assert {"experimental_unit_id"}.issubset(run_columns)
    Session = sessionmaker(bind=postgres_engine)
    with Session.begin() as session:
        prompt = Prompt(text="PostgreSQL controlled test", category="synthetic")
        session.add(prompt); session.flush()
        a, b = Answer(prompt_id=prompt.id, model_name="gpt-4", text="A", word_count=1), Answer(prompt_id=prompt.id, model_name="claude-v1", text="B", word_count=1)
        session.add_all((a, b)); session.flush()
        repo = ControlledPersistence(session)
        dataset = repo.get_or_create_dataset_version(source_name="phase85-postgres", version="v1", source_checksum="a" * 64, checksum_algorithm="SHA-256", import_status="SUCCEEDED")
        experiment = repo.create_experiment(dataset_version=dataset, experiment_name="phase85-postgres", research_question="synthetic", hypothesis="synthetic")
        condition = repo.create_condition(experiment=experiment, condition_code="POSITION_SWAP", label="position", condition_json={}, protocol_version="v1", prompt_template_version="controlled-judge-pairwise-v1")
        manifest = repo.create_manifest(experiment=experiment, rq_code="RQ3", protocol_version="v1", analysis_version="v1", dataset_snapshot_id="test", dataset_checksum="b" * 64, manifest_sha256="c" * 64, manifest_json={})
        for order in ("AB", "BA", "AB_BA", "SELF_A", "SELF_B"):
            unit = repo.register_unit(experiment=experiment, manifest=manifest, condition=condition, prompt_id=prompt.id, answer_a_id=a.id, answer_b_id=b.id, prompt_category="synthetic", judge_model="gpt-4o-mini", provider="OPENAI", provider_model="gpt-4o-mini", prompt_template_version="controlled-judge-pairwise-v1", presentation_order=order, repetition_index=len(order), randomization_block=order, data_split="test", inclusion_status="INCLUDED", temperature=Decimal("0"), top_p=Decimal("1"))
            run = repo.create_run(unit=unit, idempotency_key=(order.encode().hex() * 64)[:64], requested_model="gpt-4o-mini")
            assert run.experimental_unit_id == unit.id
