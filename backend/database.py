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
