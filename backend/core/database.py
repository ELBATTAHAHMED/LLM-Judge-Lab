import os
from typing import Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine
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

