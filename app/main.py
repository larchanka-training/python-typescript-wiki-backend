"""FastAPI application entrypoint.

- Uses `slowapi` to rate-limit public endpoints.
- Creates an `asyncpg` connection pool on startup for raw SQL queries.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated

import asyncpg
from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.exceptions import HTTPException

from app.api.v1.routes import auth as auth_routes, session as session_routes
from app.core.errors import (
    AppError,
    app_error_handler,
    http_exception_handler,
    rate_limit_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.trace import TRACE_ID_HEADER, get_or_create_trace_id
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
app.add_exception_handler(RateLimitExceeded, rate_limit_exception_handler)
# Валидация запроса всегда 400 VALIDATION_ERROR (не 422).
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


@app.middleware("http")
async def trace_id_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Attach a trace id to each request/response for debugging."""
    trace_id = get_or_create_trace_id(request)
    request.state.trace_id = trace_id
    response = await call_next(request)
    response.headers[TRACE_ID_HEADER] = trace_id
    return response


@app.get("/")
@limiter.limit("10/second")
async def root(request: Request) -> dict[str, str]:
    _ = request
    return {"message": "Hello World"}


@app.get("/health/db")
async def health_db(
    connection: Annotated[asyncpg.Connection, Depends(get_connection)],
) -> dict[str, bool]:
    """Database liveness probe."""
    return {"ok": await connection.fetchval("SELECT 1") == 1}


app.include_router(auth_routes.router)
app.include_router(session_routes.router)
