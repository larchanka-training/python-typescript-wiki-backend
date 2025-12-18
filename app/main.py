from contextlib import asynccontextmanager

import asyncpg
from fastapi import Depends, FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.db import close_pool, create_pool, get_connection


limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_pool = await create_pool()
    try:
        yield
    finally:
        await close_pool(app.state.db_pool)


app = FastAPI(lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/")
@limiter.limit("10/second")
async def root(request: Request):
    return {"message": "Hello World"}


@app.get("/health/db")
async def health_db(connection: asyncpg.Connection = Depends(get_connection)):
    return {"ok": await connection.fetchval("SELECT 1") == 1}
