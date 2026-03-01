"""SQLAlchemy модели."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from uuid import UUID  # noqa: TC003

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Tmp(Base):
    __tablename__ = "tmp"

    id: Mapped[int] = mapped_column(primary_key=True)


class User(Base):
    """User model mirrored by the users table.

    telegram_id is the stable unique identifier from oauth.name.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    photo_url: Mapped[str | None] = mapped_column(String(1024))
    permission: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )
    # updated_at — техническое время изменения записи, last_login_at — факт входа.
    last_login_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )


class Session(Base):
    """Session model stored in DB (opaque token stored as hash).

    expires_at — TTL сессии, revoked_at — отзыв; raw токен не хранится.
    """

    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )


class Space(Base):
    """Space model."""

    __tablename__ = "spaces"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delete_scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SpaceMembership(Base):
    """Link between Users and Spaces."""

    __tablename__ = "space_memberships"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    space_id: Mapped[UUID] = mapped_column(ForeignKey("spaces.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(64), nullable=False)


class Article(Base):
    """Article model."""

    __tablename__ = "articles"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    space_id: Mapped[UUID] = mapped_column(
        ForeignKey("spaces.id", ondelete="CASCADE"), index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True,
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("articles.id", ondelete="SET NULL"),
    )
    position: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("article_versions.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ArticleVersion(Base):
    """Article version model."""

    __tablename__ = "article_versions"

    __table_args__ = (
        UniqueConstraint("article_id", "version_number", name="uq_article_versions_article_id_version_number"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    article_id: Mapped[UUID] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), index=True,
    )
    version_number: Mapped[int] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True,
    )
    show_toc: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    content_format: Mapped[str] = mapped_column(String(32), server_default="markdown", nullable=False)
    change_summary: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )
