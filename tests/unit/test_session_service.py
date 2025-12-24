"""Unit tests for SessionService expiry/refresh/revoke logic."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
from typing import TYPE_CHECKING, TypeVar
from uuid import uuid4

import pytest

from app.core.errors import AppError, ErrorCode
from app.services.models import SessionRecord, UserProfile
from app.services.session_service import SessionService

if TYPE_CHECKING:
    from collections.abc import Awaitable
    from uuid import UUID

T = TypeVar("T")
SESSION_TOKEN = "session-token"  # noqa: S105


class FakeAuthService:
    """Returns a fixed user for token verification."""

    def __init__(self, user: UserProfile) -> None:
        self._user = user

    async def verify_token(self, _token: str, trace_id: str) -> tuple[UserProfile, bool]:
        _ = trace_id
        return self._user, True


class InMemorySessionRepo:
    """In-memory session storage for unit tests."""

    def __init__(self) -> None:
        self._storage: dict[str, SessionRecord] = {}

    async def create_session(
        self,
        *,
        session_id: UUID,
        user_id: int,
        token_hash: str,
        expires_at: datetime,
    ) -> SessionRecord:
        record = SessionRecord(
            id=session_id,
            user_id=user_id,
            expires_at=expires_at,
            revoked_at=None,
        )
        self._storage[token_hash] = record
        return record

    async def get_by_token_hash(self, token_hash: str) -> SessionRecord | None:
        return self._storage.get(token_hash)

    async def update_expiry(self, token_hash: str, expires_at: datetime) -> SessionRecord | None:
        record = self._storage.get(token_hash)
        if record is None:
            return None
        self._storage[token_hash] = SessionRecord(
            id=record.id,
            user_id=record.user_id,
            expires_at=expires_at,
            revoked_at=record.revoked_at,
        )
        return self._storage[token_hash]

    async def revoke(self, token_hash: str, revoked_at: datetime) -> None:
        record = self._storage.get(token_hash)
        if record is None:
            return
        self._storage[token_hash] = SessionRecord(
            id=record.id,
            user_id=record.user_id,
            expires_at=record.expires_at,
            revoked_at=revoked_at,
        )


class InMemoryUserRepo:
    """In-memory user storage for unit tests."""

    def __init__(self, user: UserProfile) -> None:
        self._user = user

    async def get_by_id(self, _user_id: int) -> UserProfile:
        return self._user


def _run(coro: Awaitable[T]) -> T:
    return asyncio.run(coro)


def _sample_user() -> UserProfile:
    now = datetime.now(timezone.utc)
    return UserProfile(
        id=1,
        telegram_id=123,
        username="user",
        first_name=None,
        last_name=None,
        photo_url=None,
        permission=None,
        created_at=now,
        last_login_at=now,
    )


def test_create_session_returns_token_and_expiry() -> None:
    user = _sample_user()
    auth = FakeAuthService(user)
    sessions = InMemorySessionRepo()
    users = InMemoryUserRepo(user)
    service = SessionService(
        auth_service=auth,
        user_repository=users,
        session_repository=sessions,
        ttl_seconds=60,
    )

    data = _run(service.create_session("oauth-token", "trace"))

    assert data.session_token
    assert data.expires_at > datetime.now(timezone.utc)


def test_get_session_expired_returns_401() -> None:
    user = _sample_user()
    auth = FakeAuthService(user)
    sessions = InMemorySessionRepo()
    users = InMemoryUserRepo(user)
    service = SessionService(
        auth_service=auth,
        user_repository=users,
        session_repository=sessions,
        ttl_seconds=60,
    )

    token = SESSION_TOKEN
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expired = datetime.now(timezone.utc) - timedelta(seconds=5)
    _run(
        sessions.create_session(
            session_id=uuid4(),
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expired,
        )
    )

    with pytest.raises(AppError) as exc_info:
        _run(service.get_session(token, "trace"))

    assert exc_info.value.code == ErrorCode.SESSION_EXPIRED


def test_refresh_extends_expiry() -> None:
    user = _sample_user()
    auth = FakeAuthService(user)
    sessions = InMemorySessionRepo()
    users = InMemoryUserRepo(user)
    service = SessionService(
        auth_service=auth,
        user_repository=users,
        session_repository=sessions,
        ttl_seconds=60,
    )

    token = SESSION_TOKEN
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires = datetime.now(timezone.utc) + timedelta(seconds=5)
    _run(
        sessions.create_session(
            session_id=uuid4(),
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires,
        )
    )

    data = _run(service.refresh_session(token, "trace"))

    assert data.expires_at > expires


def test_revoke_marks_session() -> None:
    user = _sample_user()
    auth = FakeAuthService(user)
    sessions = InMemorySessionRepo()
    users = InMemoryUserRepo(user)
    service = SessionService(
        auth_service=auth,
        user_repository=users,
        session_repository=sessions,
        ttl_seconds=60,
    )

    token = SESSION_TOKEN
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires = datetime.now(timezone.utc) + timedelta(seconds=60)
    _run(
        sessions.create_session(
            session_id=uuid4(),
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires,
        )
    )

    _run(service.revoke_session(token, "trace"))

    with pytest.raises(AppError) as exc_info:
        _run(service.get_session(token, "trace"))

    assert exc_info.value.code == ErrorCode.SESSION_EXPIRED
