from __future__ import annotations

from logging.config import fileConfig
import os

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Migrations deliberately define their own historical schema.  Importing the
# application ORM here would make replay depend on future application changes.
target_metadata = None

# An explicit Alembic-only URL avoids accidentally migrating the application's
# configured database during isolated tests. The checked-in SQLite URL remains
# an offline-test fallback.
if os.getenv("ALEMBIC_DATABASE_URL"):
    config.set_main_option("sqlalchemy.url", os.environ["ALEMBIC_DATABASE_URL"])


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
