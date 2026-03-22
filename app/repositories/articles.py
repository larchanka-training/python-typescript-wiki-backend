"""Repositories for articles."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from datetime import datetime

    import asyncpg


class ConflictError(Exception):
    """Raised when an optimistic-locking conflict is detected."""


class ArticleRepository:
    """Repository for articles (asyncpg)."""

    def __init__(self, connection: asyncpg.Connection) -> None:
        self._connection = connection

    async def create_article_with_version(
        self,
        space_id: UUID,
        title: str,
        content: str,
        owner_id: int,
        *,
        show_toc: bool = False,
        parent_id: UUID | None = None,
        position: int = 0,
    ) -> UUID:
        """Create an article and its first version atomically.

        Returns:
            UUID of the created article.
        """
        async with self._connection.transaction():
            article_id = await self._connection.fetchval(
                """
                INSERT INTO articles (id, space_id, title, owner_id, parent_id, position)
                VALUES (gen_random_uuid(), $1, $2, $3, $4, $5)
                RETURNING id;
                """,
                space_id,
                title,
                owner_id,
                parent_id,
                position,
            )

            version_id = await self._connection.fetchval(
                """
                INSERT INTO article_versions
                    (id, article_id, version_number, title, content, author_id, show_toc)
                VALUES (gen_random_uuid(), $1, 1, $2, $3, $4, $5)
                RETURNING id;
                """,
                article_id,
                title,
                content,
                owner_id,
                show_toc,
            )

            await self._connection.execute(
                """
                UPDATE articles SET version_id = $1 WHERE id = $2;
                """,
                version_id,
                article_id,
            )

            return article_id

    async def save_new_version(
        self,
        article_id: UUID,
        title: str,
        content: str,
        author_id: int,
        *,
        show_toc: bool = False,
        content_format: str = "markdown",
        change_summary: str | None = None,
        base_version_number: int | None = None,
    ) -> UUID:
        """Create a new version with SELECT FOR UPDATE protection.

        If ``base_version_number`` is provided and does not match the current
        latest version number, raises ``ConflictError``.

        Returns:
            UUID of the created version.
        """
        async with self._connection.transaction():
            # Lock the article row to prevent concurrent version creation
            row = await self._connection.fetchrow(
                """
                SELECT a.id, a.title, av.version_number
                FROM articles a
                LEFT JOIN article_versions av ON av.id = a.version_id
                WHERE a.id = $1 AND a.deleted_at IS NULL
                FOR UPDATE OF a;
                """,
                article_id,
            )
            if row is None:
                raise ValueError("Article not found")

            current_version_number = row["version_number"] or 0

            # Optimistic locking check
            if base_version_number is not None and base_version_number != current_version_number:
                raise ConflictError(
                    f"Version conflict: expected {base_version_number}, "
                    f"but current is {current_version_number}"
                )

            next_version = current_version_number + 1

            version_id = await self._connection.fetchval(
                """
                INSERT INTO article_versions
                    (id, article_id, version_number, title, content, author_id,
                     show_toc, content_format, change_summary)
                VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id;
                """,
                article_id,
                next_version,
                title,
                content,
                author_id,
                show_toc,
                content_format,
                change_summary,
            )

            # Update article pointer and title
            await self._connection.execute(
                """
                UPDATE articles
                SET version_id = $1, title = $2, updated_at = now()
                WHERE id = $3;
                """,
                version_id,
                title,
                article_id,
            )

            return version_id

    async def get_article_by_id(self, article_id: UUID) -> dict | None:
        """Return article row by id or None if not found (excludes soft-deleted)."""
        row = await self._connection.fetchrow(
            """
            SELECT a.id, a.space_id, a.title, a.owner_id, a.parent_id, a.position,
                   a.version_id, a.created_at, a.updated_at, a.deleted_at, a.is_locked,
                   u.username as owner_username, u.telegram_id as owner_telegram_id
            FROM articles a
            LEFT JOIN users u ON a.owner_id = u.id
            WHERE a.id = $1 AND a.deleted_at IS NULL;
            """,
            article_id,
        )
        return dict(row) if row else None

    async def get_articles_by_space(self, space_id: UUID, parent_id: UUID | None = None, filter_by_parent: bool = False) -> list[dict]:
        """Return list of articles in the space (for tree building)."""
        query = """
            SELECT a.id, a.space_id, a.title, a.owner_id, a.parent_id, a.position,
                   a.created_at, a.updated_at, a.is_locked,
                   u.username as owner_username, u.telegram_id as owner_telegram_id
            FROM articles a
            LEFT JOIN users u ON a.owner_id = u.id
            WHERE a.space_id = $1 AND a.deleted_at IS NULL
        """
        params = [space_id]
        if filter_by_parent:
            if parent_id is None:
                query += " AND a.parent_id IS NULL"
            else:
                query += " AND a.parent_id = $2"
                params.append(parent_id)

        query += " ORDER BY a.position, a.created_at;"
        rows = await self._connection.fetch(query, *params)
        return [dict(row) for row in rows]

    async def get_article_ancestors(self, article_id: UUID) -> list[dict]:
        """Fetch all ancestors of an article recursively (path to root) with full details."""
        rows = await self._connection.fetch(
            """
            WITH RECURSIVE ancestors AS (
                SELECT a.id, a.space_id, a.title, a.owner_id, a.parent_id, a.position,
                       a.created_at, a.updated_at, a.is_locked, 1 as level
                FROM articles a
                WHERE a.id = $1 AND a.deleted_at IS NULL
                
                UNION ALL
                
                SELECT a.id, a.space_id, a.title, a.owner_id, a.parent_id, a.position,
                       a.created_at, a.updated_at, a.is_locked, ans.level + 1
                FROM articles a
                JOIN ancestors ans ON a.id = ans.parent_id
                WHERE a.deleted_at IS NULL
            )
            SELECT ans.*, u.username as owner_username, u.telegram_id as owner_telegram_id
            FROM ancestors ans
            LEFT JOIN users u ON ans.owner_id = u.id
            ORDER BY level DESC;
            """,
            article_id,
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

    async def set_locked(self, article_id: UUID, is_locked: bool) -> None:
        """Lock or unlock an article."""
        await self._connection.execute(
            """
            UPDATE articles
            SET is_locked = $2, updated_at = now()
            WHERE id = $1;
            """,
            article_id,
            is_locked,
        )

    async def mark_deleted(self, article_id: UUID, deleted_at: datetime) -> None:
        """Soft-delete an article by setting deleted_at."""
        await self._connection.execute(
            """
            UPDATE articles
            SET deleted_at = $2
            WHERE id = $1;
            """,
            article_id,
            deleted_at,
        )

    async def get_recent_articles_by_user(self, user_id: int, limit: int = 10) -> list[dict]:
        """Fetch latest articles edited or created by user across all joined spaces."""
        rows = await self._connection.fetch(
            """
            SELECT DISTINCT ON (a.updated_at, a.id)
                   a.id, a.title, a.updated_at, a.created_at, a.space_id, 
                   s.name as space_name, a.owner_id, a.is_locked,
                   u.username as owner_username
            FROM articles a
            JOIN spaces s ON a.space_id = s.id
            JOIN space_memberships sm ON s.id = sm.space_id
            LEFT JOIN article_versions av ON a.id = av.article_id
            LEFT JOIN users u ON a.owner_id = u.id
            WHERE sm.user_id = $1
              AND (a.owner_id = $1 OR av.author_id = $1)
              AND a.deleted_at IS NULL
            ORDER BY a.updated_at DESC, a.id
            LIMIT $2;
            """,
            user_id,
            limit,
        )
        return [dict(row) for row in rows]

    async def search_articles(
        self,
        user_id: int,
        query: str,
        limit: int = 20,
    ) -> list[dict]:
        """Searches articles by title and content across member spaces.

        Args:
            user_id: ID of the user searching.
            query: Search query string.
            limit: Maximum results to return.

        Returns:
            List of dictionaries with id, title, space_id, space_name.
        """
        pattern = f"%{query}%"
        return await self._connection.fetch(
            """
            SELECT
                a.id,
                a.title,
                a.space_id,
                s.name as space_name,
                v.updated_at
            FROM articles a
            JOIN article_versions v ON a.version_id = v.id
            JOIN spaces s ON a.space_id = s.id
            JOIN space_memberships sm ON s.id = sm.space_id
            WHERE sm.user_id = $1
              AND (a.title ILIKE $2 OR v.content ILIKE $2)
            ORDER BY v.updated_at DESC
            LIMIT $3;
            """,
            user_id,
            pattern,
            limit,
        )


class ArticleVersionRepository:
    """Repository for article versions (asyncpg)."""

    def __init__(self, connection: asyncpg.Connection) -> None:
        self._connection = connection

    _SELECT_COLS = (
        "av.id, av.article_id, av.version_number, av.title, av.content, av.author_id, "
        "av.show_toc, av.content_format, av.change_summary, av.created_at, "
        "u.username as author_username, u.telegram_id as author_telegram_id"
    )

    async def get_versions_by_article(self, article_id: UUID) -> list[dict]:
        """Return list of versions for the article."""
        rows = await self._connection.fetch(
            f"""
            SELECT {self._SELECT_COLS}
            FROM article_versions av
            LEFT JOIN users u ON av.author_id = u.id
            WHERE av.article_id = $1
            ORDER BY av.version_number DESC;
            """,
            article_id,
        )
        return [dict(row) for row in rows]

    async def get_version_by_id(self, version_id: UUID) -> dict | None:
        """Return version row by id or None if not found."""
        row = await self._connection.fetchrow(
            f"""
            SELECT {self._SELECT_COLS}
            FROM article_versions av
            LEFT JOIN users u ON av.author_id = u.id
            WHERE av.id = $1;
            """,
            version_id,
        )
        return dict(row) if row else None

    async def get_version_by_number(self, article_id: UUID, version_number: int) -> dict | None:
        """Return a specific version by its ordinal number."""
        row = await self._connection.fetchrow(
            f"""
            SELECT {self._SELECT_COLS}
            FROM article_versions av
            LEFT JOIN users u ON av.author_id = u.id
            WHERE av.article_id = $1 AND av.version_number = $2;
            """,
            article_id,
            version_number,
        )
        return dict(row) if row else None

    async def get_latest_version_by_article(self, article_id: UUID) -> dict | None:
        """Return the latest version for the article."""
        row = await self._connection.fetchrow(
            f"""
            SELECT {self._SELECT_COLS}
            FROM article_versions av
            LEFT JOIN users u ON av.author_id = u.id
            WHERE av.article_id = $1
            ORDER BY av.version_number DESC
            LIMIT 1;
            """,
            article_id,
        )
        return dict(row) if row else None
