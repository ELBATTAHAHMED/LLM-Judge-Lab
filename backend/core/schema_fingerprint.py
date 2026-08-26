"""Read-only schema/count fingerprinting utility.

This utility never alters a database.  It is intended for Phase 1 pre/post
checks and accepts an engine supplied by the caller.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


IMPORTANT_TABLES = ("prompts", "answers", "human_preferences", "judge_decisions", "dataset_versions", "experiments", "experimental_conditions", "experiment_manifests", "experimental_units", "counterfactual_variants", "analysis_runs", "runs", "passes")


def fingerprint(engine: Engine) -> dict[str, Any]:
    inspector = inspect(engine)
    tables: dict[str, Any] = {}
    with engine.connect() as connection:
        counts = {name: int(connection.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar_one()) for name in IMPORTANT_TABLES if name in inspector.get_table_names()}
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none() if "alembic_version" in inspector.get_table_names() else None
    for name in IMPORTANT_TABLES:
        if name not in inspector.get_table_names():
            continue
        tables[name] = {
            "columns": [{"name": col["name"], "type": str(col["type"]), "nullable": bool(col["nullable"]), "default": str(col.get("default")) if col.get("default") is not None else None} for col in inspector.get_columns(name)],
            "primary_key": inspector.get_pk_constraint(name),
            "foreign_keys": inspector.get_foreign_keys(name),
            "unique_constraints": inspector.get_unique_constraints(name),
            "check_constraints": inspector.get_check_constraints(name),
            "indexes": inspector.get_indexes(name),
        }
    return {"dialect": engine.dialect.name, "alembic_revision": revision, "counts": counts, "tables": tables}
