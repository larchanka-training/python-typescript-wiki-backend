from contextlib import asynccontextmanager

import asyncpg
from fastapi import Depends, FastAPI

from app.db import close_pool, create_pool, get_connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_pool = await create_pool()
    try:
        yield
    finally:
        await close_pool(app.state.db_pool)


app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/health/db")
async def health_db(connection: asyncpg.Connection = Depends(get_connection)):
    return {"ok": await connection.fetchval("SELECT 1") == 1}
