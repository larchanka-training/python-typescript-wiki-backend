"""SQLAlchemy models.

Right now this module contains a single `tmp` table used as a migration example.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Tmp(Base):
    __tablename__ = "tmp"

    id: Mapped[int] = mapped_column(primary_key=True)
