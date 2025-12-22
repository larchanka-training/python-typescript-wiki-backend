"""Alembic environment configuration.

- Loads SQLAlchemy metadata from `app.models`.
- Uses `DATABASE_URL` to connect to Postgres.
- Ensures the URL uses the `psycopg` driver for SQLAlchemy (`postgresql+psycopg://`).
"""

from __future__ import annotations

from logging.config import fileConfig
import os

from sqlalchemy import create_engine, pool
from sqlalchemy.engine import URL, make_url

from alembic import context
from app.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_sqlalchemy_url() -> URL:
    """Build SQLAlchemy URL from env/config and enforce psycopg driver."""
    raw_url = os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
    url = make_url(raw_url)
    if url.drivername == "postgresql":
        # Some tools/environments provide `postgresql://...`; SQLAlchemy needs an explicit driver.
        url = url.set(drivername="postgresql+psycopg")
    return url


def run_migrations_offline() -> None:
    """Run migrations in offline mode (no DB connection)."""
    url = get_sqlalchemy_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with an active DB connection."""
    connectable = create_engine(get_sqlalchemy_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
