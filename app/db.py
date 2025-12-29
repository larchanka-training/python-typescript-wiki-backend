"""Database helpers.

The project uses `asyncpg` for "clean" (raw) SQL queries.
Connection settings are read from `DATABASE_URL`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator  # noqa: TC003
import os

import asyncpg
from fastapi import Request

# Default value is suitable for local development.
DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/postgres"


def get_database_url() -> str:
    """Return DB URL from env with a local-dev fallback."""
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


async def create_pool() -> asyncpg.Pool:
    """Create an asyncpg pool for the whole application."""
    return await asyncpg.create_pool(dsn=get_database_url(), min_size=1, max_size=10)


async def close_pool(pool: asyncpg.Pool) -> None:
    """Close the asyncpg pool on application shutdown."""
    await pool.close()


async def get_connection(request: Request) -> AsyncIterator[asyncpg.Connection]:
    """FastAPI dependency that yields a pooled connection."""
    pool: asyncpg.Pool | None = getattr(request.app.state, "db_pool", None)
    if pool is None:
        msg = "Database pool is not initialized"
        raise RuntimeError(msg)
    async with pool.acquire() as connection:
        yield connection
