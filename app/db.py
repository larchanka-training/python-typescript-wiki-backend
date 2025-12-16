import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def get_database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://admin:admin123@postgres:5432/wiki",
    )


engine = create_engine(get_database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass

