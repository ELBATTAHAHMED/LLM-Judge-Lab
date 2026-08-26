"""Regression coverage for the database-independent canonical source dataset."""
from __future__ import annotations

from copy import deepcopy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.data.canonical import CanonicalSourceError, build_fresh_dataset, compare_canonical_to_frozen_reconciliation, load_canonical_study, stable_sha, validate_canonical_source, verify_fresh_dataset
from backend.core.database import Base


ROOT = Path(__file__).resolve().parents[2]


def test_committed_canonical_source_validates_all_records():
    payload, source = validate_canonical_source()

    assert len(payload["records"]) == 1568
    assert source.raw_sha256 == payload["raw_source"]["sha256"]


def test_canonical_records_match_the_frozen_source_reconciliation():
    assert compare_canonical_to_frozen_reconciliation() == {
        "canonical_logical_identities": 1568,
        "source_hash_matches": 1568,
        "source_hash_mismatches": 0,
    }


def test_canonical_answer_hash_mismatch_fails_closed():
    payload = deepcopy(load_canonical_study())
    payload["records"][0]["answers"][0]["text_sha256"] = "0" * 64
    payload["canonical_dataset_sha256"] = stable_sha({key: value for key, value in payload.items() if key != "canonical_dataset_sha256"})

    with pytest.raises(CanonicalSourceError, match="SOURCE_TEXT_HASH_MISMATCH"):
        validate_canonical_source(payload)


def test_empty_database_build_is_source_keyed_and_reconciles_all_records():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        report = build_fresh_dataset(session)
        session.commit()
        verification = verify_fresh_dataset(session)
    finally:
        session.close()

    assert report["controlled_records"] == 1568
    assert report["source_exact"] == 1070
    assert report["source_correction_required"] == 498
    assert report["distinct_mt_bench_questions"] == 80
    assert report["question_id_min"] == 81
    assert report["question_id_max"] == 160
    assert report["turn_1_prompt_records"] == 80
    assert report["turn_2_prompt_records"] == 80
    assert report["turn_level_prompt_records"] == 160
    assert "prompts" not in report
    assert verification == {
        "source_hash_matches": 1568,
        "source_hash_mismatches": 0,
        "controlled_records": 1568,
        "unresolved": 0,
    }


def test_public_planning_script_runs_directly_without_provider_calls(tmp_path):
    database_path = tmp_path / "canonical-cli.sqlite"
    database_url = f"sqlite:///{database_path.as_posix()}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        build_fresh_dataset(session)
        session.commit()
    finally:
        session.close()
        engine.dispose()

    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_evaluation.py"), "--limit", "2"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["provider_calls"] == 0


def test_public_analysis_script_verifies_frozen_artifact_without_provider_calls():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_analysis.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "VERIFIED"
    assert payload["provider_calls"] == 0
    assert payload["analysis_artifact_sha256"] == "ace75cfb15412c2070b848f048ad419ae70d46162c7b66d52ee4302432031d97"

