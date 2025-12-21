"""FastAPI application entrypoint.

- Uses `slowapi` to rate-limit public endpoints.
- Creates an `asyncpg` connection pool on startup for raw SQL queries.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

import asyncpg
from fastapi import Depends, FastAPI
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.db import close_pool, create_pool, get_connection

# Global rate limiter instance. Per-route limits are configured via decorators.
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifecycle hooks: init/teardown asyncpg pool."""
    app.state.db_pool = await create_pool()
    try:
        yield
    finally:
        await close_pool(app.state.db_pool)


app = FastAPI(lifespan=lifespan)

# slowapi reads limiter from app.state and uses the exception handler for 429 responses.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/")
@limiter.limit("10/second")
async def root() -> dict[str, str]:
    return {"message": "Hello World"}


@app.get("/health/db")
async def health_db(
    connection: Annotated[asyncpg.Connection, Depends(get_connection)],
) -> dict[str, bool]:
    """Database liveness probe."""
    return {"ok": await connection.fetchval("SELECT 1") == 1}
