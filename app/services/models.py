"""Модели данных сервисного слоя."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID


@dataclass
class UserProfile:
    """Профиль пользователя, возвращаемый сервисным слоем."""

    id: int
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    photo_url: str | None
    permission: str | None
    created_at: datetime
    last_login_at: datetime


@dataclass
class SessionRecord:
    """Сессия из БД (без raw токена)."""

    id: UUID
    user_id: int
    expires_at: datetime
    revoked_at: datetime | None


@dataclass
class SessionData:
    """Данные сессии, возвращаемые сервисным слоем."""

    user: UserProfile
    expires_at: datetime
    session_token: str | None = None
