from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
import sys
sys.path.insert(0, str(BACKEND))

from controlled_models import AnalysisRun, ControlledRun, CounterfactualVariant, DatasetVersion, Experiment, ExperimentalCondition, ExperimentManifest, ExperimentalUnit, RunPass
from controlled_persistence import ControlledPersistence, Outcome, PassObservation
from models import Answer, Prompt
from schema_fingerprint import fingerprint


@pytest.fixture()
def isolated_engine(tmp_path):
    db_path = tmp_path / "phase1.sqlite"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    event.listen(engine, "connect", lambda dbapi_connection, _: dbapi_connection.execute("PRAGMA foreign_keys=ON"))
    try:
        yield engine
    finally:
        engine.dispose()


def _legacy_pair(session):
    prompt = Prompt(text="Which response is better?", category="test")
    session.add(prompt)
    session.flush()
    answer_a = Answer(prompt_id=prompt.id, model_name="model-a", text="A", word_count=1)
    answer_b = Answer(prompt_id=prompt.id, model_name="model-b", text="B", word_count=1)
    session.add_all([answer_a, answer_b])
    session.flush()
    return prompt, answer_a, answer_b


def _controlled_fixture(session):
    prompt, answer_a, answer_b = _legacy_pair(session)
    repo = ControlledPersistence(session)
    dataset = repo.get_or_create_dataset_version(source_name="test-dataset", version="v1", source_checksum="a" * 64, checksum_algorithm="SHA-256", import_status="SUCCEEDED")
    experiment = repo.create_experiment(dataset_version=dataset, experiment_name="offline provenance", research_question="RQ1", hypothesis="offline persistence")
    condition = repo.create_condition(experiment=experiment, condition_code="POSITION_SWAP", label="swap", condition_json={"variant": "POSITION_SWAP"}, protocol_version="p1", prompt_template_version="judge-v1")
    manifest = repo.create_manifest(experiment=experiment, rq_code="RQ1", protocol_version="p1", analysis_version="a1", dataset_snapshot_id="snapshot-1", dataset_checksum="b" * 64, manifest_sha256="c" * 64, manifest_json={"provider_execution": "not_run"})
    unit = repo.register_unit(experiment=experiment, manifest=manifest, condition=condition, prompt_id=prompt.id, answer_a_id=answer_a.id, answer_b_id=answer_b.id, prompt_category=prompt.category, judge_model="requested-judge", provider="fake-provider", provider_model="fake/model", prompt_template_version="judge-v1", presentation_order="AB", repetition_index=2, randomization_block="block-1", data_split="test", inclusion_status="INCLUDED", pairing_key=hashlib.sha256(b"pair").hexdigest())
    return repo, dataset, experiment, manifest, unit, answer_a, answer_b


def test_fresh_migration_reaches_recovered_controlled_schema(isolated_engine):
    inspection = inspect(isolated_engine)
    required = {"dataset_versions", "experiments", "experimental_conditions", "experiment_manifests", "experimental_units", "counterfactual_variants", "analysis_runs", "runs", "passes"}
    assert required.issubset(set(inspection.get_table_names()))
    with isolated_engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0009_multijudge_execution_ledger"
    run_columns = {column["name"] for column in inspection.get_columns("runs")}
    assert {"requested_model", "effective_model", "provider", "repetition_index", "final_parse_status", "legacy_decision_id", "experimental_unit_id"}.issubset(run_columns)


def test_controlled_orm_column_contract_matches_migrations(isolated_engine):
    inspection = inspect(isolated_engine)
    for model in (DatasetVersion, Experiment, ExperimentalCondition, ExperimentManifest, ExperimentalUnit, CounterfactualVariant, AnalysisRun, ControlledRun, RunPass):
        database_columns = {column["name"] for column in inspection.get_columns(model.__tablename__)}
        assert database_columns == set(model.__table__.columns.keys()), model.__tablename__


def test_dataset_experiment_unit_run_two_pass_round_trip(isolated_engine):
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        repo, dataset, experiment, manifest, unit, answer_a, answer_b = _controlled_fixture(session)
        run = repo.create_run(unit=unit, idempotency_key="d" * 64, requested_model="requested/model", effective_model="returned/model", model_version="2026-01", run_kind="CALIBRATED_DUAL_PASS")
        repo.mark_running(run)
        first = repo.record_pass(run=run, observation=PassObservation(1, answer_a.id, answer_b.id, Outcome.ANSWER_A, effective_model="returned/model"))
        second = repo.record_pass(run=run, observation=PassObservation(2, answer_b.id, answer_a.id, Outcome.ANSWER_B, effective_model="returned/model"))
        repo.complete_run(run=run, outcome=Outcome.ANSWER_A)
        assert first.winner_answer_id == answer_a.id
        assert second.winner_answer_id == answer_a.id
        assert run.metadata_json["controlled_unit_id"] == str(unit.id)
        assert run.requested_model == "requested/model"
        assert run.effective_model == "returned/model"
        run_id = run.id
        answer_a_id = answer_a.id
        answer_b_id = answer_b.id
    with Session() as session:
        loaded = session.get(ControlledRun, run_id)
        assert loaded is not None
        assert len(loaded.passes) == 2
        assert loaded.passes[0].presented_answer_a_id == answer_a_id
        assert loaded.passes[1].presented_answer_a_id == answer_b_id
        assert loaded.final_winner_answer_id == answer_a_id


@pytest.mark.parametrize(
    ("outcome", "expected_result", "expected_parse", "expected_status"),
    [
        (Outcome.ANSWER_A, "ANSWER_A", "PARSED", "SUCCEEDED"),
        (Outcome.ANSWER_B, "ANSWER_B", "PARSED", "SUCCEEDED"),
        (Outcome.TIE, "TIE", "PARSED", "SUCCEEDED"),
        (Outcome.UNKNOWN, "UNKNOWN", "MISSING_RESPONSE", "SUCCEEDED"),
        (Outcome.INVALID_RESPONSE, "ERROR", "INVALID", "FAILED"),
        (Outcome.API_ERROR, "ERROR", "PROVIDER_ERROR", "FAILED"),
        (Outcome.TIMEOUT, "ERROR", "TIMEOUT", "FAILED"),
    ],
)
def test_outcomes_remain_distinct(isolated_engine, outcome, expected_result, expected_parse, expected_status):
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        repo, _, _, _, unit, answer_a, answer_b = _controlled_fixture(session)
        run = repo.create_run(unit=unit, idempotency_key=hashlib.sha256(outcome.value.encode()).hexdigest(), requested_model="requested")
        observed = repo.record_pass(run=run, observation=PassObservation(1, answer_a.id, answer_b.id, outcome))
        repo.complete_run(run=run, outcome=outcome)
        assert run.final_result_type == expected_result
        assert run.final_parse_status == expected_parse
        assert run.status == expected_status
        assert observed.raw_verdict == expected_result
        assert observed.parse_status == expected_parse
        assert (run.final_winner_answer_id is None) == (outcome not in {Outcome.ANSWER_A, Outcome.ANSWER_B})


def test_controlled_round_trip_does_not_require_legacy_judge_decisions(isolated_engine):
    Session = sessionmaker(bind=isolated_engine)
    before = fingerprint(isolated_engine)["counts"]["judge_decisions"]
    with Session.begin() as session:
        repo, _, _, _, unit, _, _ = _controlled_fixture(session)
        repo.create_run(unit=unit, idempotency_key="e" * 64, requested_model="requested")
    after = fingerprint(isolated_engine)["counts"]["judge_decisions"]
    assert before == after == 0


def test_idempotency_and_database_constraints_work(isolated_engine):
    Session = sessionmaker(bind=isolated_engine)
    with Session.begin() as session:
        repo, _, _, _, unit, answer_a, answer_b = _controlled_fixture(session)
        first = repo.create_run(unit=unit, idempotency_key="f" * 64, requested_model="requested")
        second = repo.create_run(unit=unit, idempotency_key="f" * 64, requested_model="requested")
        assert first.id == second.id
        run_id = first.id
        answer_a_id = answer_a.id
        answer_b_id = answer_b.id

    with Session() as session:
        run = session.get(ControlledRun, run_id)
        assert run is not None
        invalid = RunPass(run_id=run.id, pass_number=0, presented_answer_a_id=answer_a_id, presented_answer_b_id=answer_b_id, raw_verdict="ANSWER_A", winner_answer_id=answer_a_id, parse_status="PARSED")
        session.add(invalid)
        with pytest.raises(IntegrityError):
            session.commit()
