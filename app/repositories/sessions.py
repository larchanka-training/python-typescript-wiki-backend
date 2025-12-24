"""Репозиторий сессий (asyncpg)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.services.models import SessionRecord

if TYPE_CHECKING:
    from uuid import UUID

    import asyncpg


class SessionRepository:
    """Репозиторий сессий (asyncpg).

    Токен хранится как sha256-хэш, индексы по user_id/expires_at ускоряют проверки TTL.
    """

    def __init__(self, connection: asyncpg.Connection) -> None:
        self._connection = connection

    async def create_session(
        self,
        *,
        session_id: UUID,
        user_id: int,
        token_hash: str,
        expires_at: datetime,
    ) -> SessionRecord:
        """Создаёт запись сессии и возвращает её."""
        row = await self._connection.fetchrow(
            """
            INSERT INTO sessions (
                id,
                user_id,
                token_hash,
                expires_at
            )
            VALUES ($1, $2, $3, $4)
            RETURNING
                id,
                user_id,
                expires_at,
                revoked_at;
            """,
            session_id,
            user_id,
            token_hash,
            expires_at,
        )
        if row is None:
            msg = "Failed to create session"
            raise RuntimeError(msg)
        return _row_to_session(row)

    async def get_by_token_hash(self, token_hash: str) -> SessionRecord | None:
        """Ищет сессию по хэшу токена (raw токен в БД не хранится)."""
        row = await self._connection.fetchrow(
            """
            SELECT
                id,
                user_id,
                expires_at,
                revoked_at
            FROM sessions
            WHERE token_hash = $1;
            """,
            token_hash,
        )
        if row is None:
            return None
        return _row_to_session(row)

    async def update_expiry(self, token_hash: str, expires_at: datetime) -> SessionRecord | None:
        """Обновляет expires_at и возвращает запись."""
        now = datetime.now(timezone.utc)
        row = await self._connection.fetchrow(
            """
            UPDATE sessions
            SET expires_at = $2,
                updated_at = $3
            WHERE token_hash = $1
            RETURNING
                id,
                user_id,
                expires_at,
                revoked_at;
            """,
            token_hash,
            expires_at,
            now,
        )
        if row is None:
            return None
        return _row_to_session(row)

    async def revoke(self, token_hash: str, revoked_at: datetime) -> None:
        """Отзывает сессию через revoked_at."""
        await self._connection.execute(
            """
            UPDATE sessions
            SET revoked_at = $2,
                updated_at = $2
            WHERE token_hash = $1;
            """,
            token_hash,
            revoked_at,
        )


def _row_to_session(row: object) -> SessionRecord:
    return SessionRecord(
        id=row["id"],
        user_id=row["user_id"],
        expires_at=row["expires_at"],
        revoked_at=row["revoked_at"],
    )
