"""Репозиторий пользователей (asyncpg)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.services.models import UserProfile

if TYPE_CHECKING:
    import asyncpg


class UserRepository:
    """Репозиторий пользователей (asyncpg)."""

    def __init__(self, connection: asyncpg.Connection) -> None:
        self._connection = connection

    async def upsert_user(  # noqa: PLR0913
        self,
        *,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        photo_url: str | None,
        permission: str | None,
    ) -> tuple[UserProfile, bool]:
        """Upsert пользователя по telegram_id.

        username обновляется при наличии входного значения, last_login_at обновляется всегда.
        updated_at — техническое поле, last_login_at — бизнес-факт входа.
        """
        now = datetime.now(timezone.utc)
        # Upsert по telegram_id гарантирует единственность пользователя.
        row = await self._connection.fetchrow(
            """
            INSERT INTO users (
                telegram_id,
                username,
                first_name,
                last_name,
                photo_url,
                permission,
                created_at,
                updated_at,
                last_login_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $7, $7)
            ON CONFLICT (telegram_id) DO UPDATE SET
                username = COALESCE(EXCLUDED.username, users.username),
                first_name = COALESCE(EXCLUDED.first_name, users.first_name),
                last_name = COALESCE(EXCLUDED.last_name, users.last_name),
                photo_url = COALESCE(EXCLUDED.photo_url, users.photo_url),
                permission = COALESCE(EXCLUDED.permission, users.permission),
                updated_at = EXCLUDED.updated_at, -- техническое время изменения записи
                last_login_at = EXCLUDED.last_login_at -- бизнес-факт последнего входа
            RETURNING
                id,
                telegram_id,
                username,
                first_name,
                last_name,
                photo_url,
                permission,
                is_superuser,
                created_at,
                updated_at,
                last_login_at,
                (xmax = 0) AS created;
            """,
            telegram_id,
            username,
            first_name,
            last_name,
            photo_url,
            permission,
            now,
        )
        if row is None:
            msg = "Failed to upsert user"
            raise RuntimeError(msg)

        user = UserProfile(
            id=row["id"],
            telegram_id=row["telegram_id"],
            username=row["username"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            photo_url=row["photo_url"],
            permission=row["permission"],
            is_superuser=row["is_superuser"],
            created_at=row["created_at"],
            last_login_at=row["last_login_at"],
        )
        return user, row["created"]

    async def get_by_id(self, user_id: int) -> UserProfile | None:
        """Return user by id or None if not found."""
        row = await self._connection.fetchrow(
            """
            SELECT
                id,
                telegram_id,
                username,
                first_name,
                last_name,
                photo_url,
                permission,
                is_superuser,
                created_at,
                updated_at,
                last_login_at
            FROM users
            WHERE id = $1;
            """,
            user_id,
        )
        if row is None:
            return None

        return UserProfile(
            id=row["id"],
            telegram_id=row["telegram_id"],
            username=row["username"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            photo_url=row["photo_url"],
            permission=row["permission"],
            is_superuser=row["is_superuser"],
            created_at=row["created_at"],
            last_login_at=row["last_login_at"],
        )

    async def ensure_first_superuser(self, user_id: int) -> bool:
        """Делает пользователя superuser, если в системе его ещё нет."""
        row = await self._connection.fetchrow(
            """
            UPDATE users
            SET is_superuser = TRUE
            WHERE id = $1
              AND NOT EXISTS (
                SELECT 1 FROM users WHERE is_superuser = TRUE
              )
            RETURNING id;
            """,
            user_id,
        )
        return row is not None
