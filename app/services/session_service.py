# ruff: noqa: RUF002, RUF003
"""Бизнес-логика работы с сессиями."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import logging
import secrets
from typing import TYPE_CHECKING
from uuid import uuid4

from fastapi import status

from app.core.errors import AppError, ErrorCode
from app.services.models import SessionData, SessionRecord, UserProfile

if TYPE_CHECKING:
    from app.repositories.sessions import SessionRepository
    from app.repositories.users import UserRepository
    from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)


class SessionService:
    """Stateful-сессии в БД с хранением хэша токена (без raw значения).

    Выбранный вариант позволяет отзывать сессию и контролировать TTL на сервере.
    """

    def __init__(
        self,
        *,
        auth_service: AuthService,
        user_repository: UserRepository,
        session_repository: SessionRepository,
        ttl_seconds: int,
    ) -> None:
        self._auth_service = auth_service
        self._user_repository = user_repository
        self._session_repository = session_repository
        self._ttl_seconds = ttl_seconds

    async def create_session(self, token: str, trace_id: str) -> SessionData:
        """Проверяет oauth токен, делает upsert пользователя, создаёт сессию."""
        # Не логируем raw oauth token; используем только trace_id/telegram_id.
        user, _created = await self._auth_service.verify_token(token, trace_id)
        session_token = _generate_token()
        # В БД сохраняем только хэш, raw session token возвращается клиенту.
        token_hash = _hash_token(session_token)
        expires_at = _expires_at(self._ttl_seconds)

        try:
            await self._session_repository.create_session(
                session_id=uuid4(),
                user_id=user.id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
        except Exception as exc:
            logger.exception("session create failed: user_id=%s trace_id=%s", user.id, trace_id)
            raise AppError(status.HTTP_500_INTERNAL_SERVER_ERROR, ErrorCode.INTERNAL_ERROR) from exc

        logger.info("session created: user_id=%s trace_id=%s", user.id, trace_id)
        return SessionData(user=user, expires_at=expires_at, session_token=session_token)

    async def get_session(self, session_token: str, trace_id: str) -> SessionData:
        """Возвращает сессию и пользователя по session token."""
        record = await self._get_session_record(session_token, trace_id)
        user = await self._get_user(record, trace_id)
        return SessionData(user=user, expires_at=record.expires_at)

    async def refresh_session(self, session_token: str, trace_id: str) -> SessionData:
        """Продлевает TTL сессии и возвращает новый expires_at."""
        record = await self._get_session_record(session_token, trace_id)
        new_expires_at = _expires_at(self._ttl_seconds)
        try:
            updated = await self._session_repository.update_expiry(
                _hash_token(session_token),
                new_expires_at,
            )
        except Exception as exc:
            logger.exception("session refresh failed: session_id=%s trace_id=%s", record.id, trace_id)
            raise AppError(status.HTTP_500_INTERNAL_SERVER_ERROR, ErrorCode.INTERNAL_ERROR) from exc
        if updated is None:
            raise AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.SESSION_MISSING)
        user = await self._get_user(record, trace_id)
        return SessionData(user=user, expires_at=new_expires_at)

    async def revoke_session(self, session_token: str, trace_id: str) -> None:
        """Отзывает сессию (revoked_at) — после этого GET /session = SESSION_EXPIRED."""
        record = await self._get_session_record(session_token, trace_id)
        now = datetime.now(timezone.utc)
        try:
            await self._session_repository.revoke(_hash_token(session_token), now)
        except Exception as exc:
            logger.exception("session revoke failed: session_id=%s trace_id=%s", record.id, trace_id)
            raise AppError(status.HTTP_500_INTERNAL_SERVER_ERROR, ErrorCode.INTERNAL_ERROR) from exc
        logger.info("session revoked: session_id=%s trace_id=%s", record.id, trace_id)

    async def _get_session_record(self, session_token: str, trace_id: str) -> SessionRecord:
        _ = trace_id
        token_hash = _hash_token(session_token)
        record = await self._session_repository.get_by_token_hash(token_hash)
        if record is None:
            raise AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.SESSION_MISSING)
        _ensure_active(record)
        return record

    async def _get_user(self, record: SessionRecord, trace_id: str) -> UserProfile:
        user = await self._user_repository.get_by_id(record.user_id)
        if user is None:
            logger.exception("session has no user: user_id=%s trace_id=%s", record.user_id, trace_id)
            raise AppError(status.HTTP_500_INTERNAL_SERVER_ERROR, ErrorCode.INTERNAL_ERROR)
        return user


def _ensure_active(record: SessionRecord) -> None:
    # Сессия считается неактивной при revoked_at или истёкшем expires_at.
    now = datetime.now(timezone.utc)
    if record.revoked_at is not None:
        raise AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.SESSION_EXPIRED)
    if record.expires_at <= now:
        raise AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.SESSION_EXPIRED)


def _expires_at(ttl_seconds: int) -> datetime:
    # TTL считается в UTC и сравнивается с expires_at.
    return datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)


def _hash_token(token: str) -> str:
    # Храним только sha256(token) для возможности отзыва без хранения raw значения.
    return hashlib.sha256(token.encode()).hexdigest()


def _generate_token() -> str:
    # Не логируем raw session token; он хранится только у клиента.
    return secrets.token_urlsafe(32)
