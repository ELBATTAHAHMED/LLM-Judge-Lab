import os
from typing import Any, Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Load environment variables from .env file if present
load_dotenv()

# Retrieve database URL from environment variables, defaulting to a standard PostgreSQL local setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/judgelab")

# Special handling for SQLite if used in local development/testing environments
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
else:
    connect_args["connect_timeout"] = 3  # Fast 3s timeout to prevent hanging connections

# Create the SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,  # Enable connection health checks (reconnects on drop)
)

# Create the session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Declarative Base class using SQLAlchemy v2.0+ class hierarchy
class Base(DeclarativeBase):
    pass

# Dependency to provide a database session lifecycle to FastAPI routes
def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def resync_postgres_sequences(target_engine=engine):
    """
    Resynchronizes PostgreSQL PRIMARY KEY auto-increment sequences with the maximum
    ID currently present in each table. Prevents UniqueViolation primary key errors.
    """
    if str(target_engine.url).startswith("sqlite"):
        return

    tables = ["prompts", "answers", "human_preferences", "judge_decisions"]
    from sqlalchemy import text
    try:
        with target_engine.connect() as conn:
            with conn.begin():
                for tbl in tables:
                    try:
                        seq_sql = f"SELECT setval(pg_get_serial_sequence('{tbl}', 'id'), COALESCE((SELECT MAX(id) FROM {tbl}), 0) + 1, false)"
                        conn.execute(text(seq_sql))
                    except Exception:
                        pass
    except Exception as e:
        print(f"Warning: Could not resync postgres sequences: {e}")


IMPORTANT_TABLES = (
    "prompts",
    "answers",
    "human_preferences",
    "judge_decisions",
    "dataset_versions",
    "experiments",
    "experimental_conditions",
    "experiment_manifests",
    "experimental_units",
    "counterfactual_variants",
    "analysis_runs",
    "runs",
    "passes",
)


def fingerprint(target_engine: Engine = engine) -> dict[str, Any]:
    """Read-only schema and table row-count fingerprinting utility."""
    from sqlalchemy import inspect, text
    inspector = inspect(target_engine)
    tables: dict[str, Any] = {}
    with target_engine.connect() as connection:
        counts = {
            name: int(connection.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar_one())
            for name in IMPORTANT_TABLES
            if name in inspector.get_table_names()
        }
        revision = (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
            if "alembic_version" in inspector.get_table_names()
            else None
        )
    for name in IMPORTANT_TABLES:
        if name not in inspector.get_table_names():
            continue
        tables[name] = {
            "columns": [
                {
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": bool(col["nullable"]),
                    "default": str(col.get("default")) if col.get("default") is not None else None,
                }
                for col in inspector.get_columns(name)
            ],
            "primary_key": inspector.get_pk_constraint(name),
            "foreign_keys": inspector.get_foreign_keys(name),
            "unique_constraints": inspector.get_unique_constraints(name),
            "check_constraints": inspector.get_check_constraints(name),
            "indexes": inspector.get_indexes(name),
        }
    return {
        "dialect": target_engine.dialect.name,
        "alembic_revision": revision,
        "counts": counts,
        "tables": tables,
    }

