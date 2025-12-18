from __future__ import annotations

import os
from collections.abc import AsyncIterator

import asyncpg
from asyncpg import Pool
from fastapi import Request


DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/postgres"


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


async def create_pool() -> Pool:
    return await asyncpg.create_pool(dsn=get_database_url(), min_size=1, max_size=10)


async def close_pool(pool: Pool) -> None:
    await pool.close()


async def get_connection(request: Request) -> AsyncIterator[asyncpg.Connection]:
    pool: Pool | None = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise RuntimeError("Database pool is not initialized")
    async with pool.acquire() as connection:
        yield connection
