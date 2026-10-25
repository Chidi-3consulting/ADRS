"""
SafeData Alembic Migration Environment.

Connects Alembic to the SQLAlchemy models defined in app.models,
enabling schema evolution for production databases.
"""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Add the project root to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, _db_url as APP_DB_URL
import app.models  # noqa: F401 — ensure all models are registered

# Alembic Config object
config = context.config

# Override the sqlalchemy.url from the app config
config.set_main_option("sqlalchemy.url", config.get_main_option("sqlalchemy.url_override") or APP_DB_URL)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    # Keep the application's own loggers on: by default fileConfig disables every logger
    # created before it runs, which silenced errors from `python -m app.cli create-admin`.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Target metadata for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — generates SQL script without DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connects to DB and applies directly."""
    section = dict(config.get_section(config.config_ini_section, {}))
    section.pop("sqlalchemy.url_override", None)  # our own option, not an engine kwarg
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
