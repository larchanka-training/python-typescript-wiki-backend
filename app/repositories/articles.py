"""Repositories for articles."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    import asyncpg


class ArticleRepository:
    """Repository for articles (asyncpg)."""

    def __init__(self, connection: asyncpg.Connection) -> None:
        self._connection = connection

    async def create_article(self, space_id: UUID, title: str, author_id: int) -> UUID:
        """Create a new article.

        Returns:
            UUID of the created article.
        """
        article_id = await self._connection.fetchval(
            """
            INSERT INTO articles (id, space_id, title, author_id)
            VALUES (gen_random_uuid(), $1, $2, $3)
            RETURNING id;
            """,
            space_id,
            title,
            author_id,
        )
        return article_id

    async def get_article_by_id(self, article_id: UUID) -> dict | None:
        """Return article row by id or None if not found."""
        row = await self._connection.fetchrow(
            """
            SELECT id, space_id, title, author_id, created_at, updated_at, deleted_at
            FROM articles
            WHERE id = $1 AND deleted_at IS NULL;
            """,
            article_id,
        )
        return dict(row) if row else None

    async def get_articles_by_space(self, space_id: UUID) -> list[dict]:
        """Return list of articles in the space."""
        rows = await self._connection.fetch(
            """
            SELECT id, space_id, title, author_id, created_at, updated_at
            FROM articles
            WHERE space_id = $1 AND deleted_at IS NULL
            ORDER BY created_at DESC;
            """,
            space_id,
        )
        return [dict(row) for row in rows]

    async def update_article_title(self, article_id: UUID, title: str) -> None:
        """Update the title of an existing article and touch updated_at."""
        await self._connection.execute(
            """
            UPDATE articles
            SET title = $1, updated_at = now()
            WHERE id = $2;
            """,
            title,
            article_id,
        )


class ArticleVersionRepository:
    """Repository for article versions (asyncpg)."""

    def __init__(self, connection: asyncpg.Connection) -> None:
        self._connection = connection

    async def create_version(self, article_id: UUID, version_number: int, title: str, content: str, author_id: int) -> UUID:
        """Create a new article version.

        Returns:
            UUID of the created version.
        """
        version_id = await self._connection.fetchval(
            """
            INSERT INTO article_versions (id, article_id, version_number, title, content, author_id)
            VALUES (gen_random_uuid(), $1, $2, $3, $4, $5)
            RETURNING id;
            """,
            article_id,
            version_number,
            title,
            content,
            author_id,
        )
        return version_id

    async def get_versions_by_article(self, article_id: UUID) -> list[dict]:
        """Return list of versions for the article."""
        rows = await self._connection.fetch(
            """
            SELECT id, article_id, version_number, title, content, author_id, created_at
            FROM article_versions
            WHERE article_id = $1
            ORDER BY version_number DESC;
            """,
            article_id,
        )
        return [dict(row) for row in rows]

    async def get_version_by_id(self, version_id: UUID) -> dict | None:
        """Return version row by id or None if not found."""
        row = await self._connection.fetchrow(
            """
            SELECT id, article_id, version_number, title, content, author_id, created_at
            FROM article_versions
            WHERE id = $1;
            """,
            version_id,
        )
        return dict(row) if row else None

    async def get_latest_version_by_article(self, article_id: UUID) -> dict | None:
        """Return the latest version for the article."""
        row = await self._connection.fetchrow(
            """
            SELECT id, article_id, version_number, title, content, author_id, created_at
            FROM article_versions
            WHERE article_id = $1
            ORDER BY version_number DESC
            LIMIT 1;
            """,
            article_id,
        )
        return dict(row) if row else None
