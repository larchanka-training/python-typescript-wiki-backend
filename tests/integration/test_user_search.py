"""Integration tests for user search endpoint."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from app.api.deps import get_session_service, get_user_service
from app.core.errors import AppError, ErrorCode
from app.main import app
from app.services.models import SessionData, UserProfile

if TYPE_CHECKING:
    from app.services.session_service import SessionService
    from app.services.user_service import UserService


@asynccontextmanager
async def _no_lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Disable lifespan to avoid DB/http client setup during tests."""
    yield


class FakeSessionService:
    """Test double for SessionService."""

    def __init__(self, user: UserProfile) -> None:
        self._user = user

    async def get_session(self, token: str, trace_id: str) -> SessionData:
        if token == "valid-token":
            return SessionData(user=self._user, expires_at=datetime.now(timezone.utc))
        if token == "expired-token":
            raise AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.SESSION_EXPIRED)
        raise AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.SESSION_MISSING)


class FakeUserService:
    """Test double for UserService."""

    def __init__(self, users: list[UserProfile]) -> None:
        self._users = users

    async def search_users(self, query: str, limit: int) -> list[UserProfile]:
        return self._users[:limit]


@pytest.fixture
def client_factory() -> Callable[[object, object], TestClient]:
    """Build a TestClient with service overrides."""
    original_lifespan = app.router.lifespan_context

    def _factory(session_service: object, user_service: object) -> TestClient:
        app.dependency_overrides[get_session_service] = lambda: session_service
        app.dependency_overrides[get_user_service] = lambda: user_service
        app.router.lifespan_context = _no_lifespan
        return TestClient(app)

    yield _factory
    app.dependency_overrides.clear()
    app.router.lifespan_context = original_lifespan


def _sample_user() -> UserProfile:
    now = datetime.now(timezone.utc)
    return UserProfile(
        id=1,
        telegram_id=123,
        username="testuser",
        first_name="First",
        last_name="Last",
        photo_url=None,
        permission=None,
        created_at=now,
        last_login_at=now,
    )


def test_search_users_success(client_factory):
    user = _sample_user()
    session_service = FakeSessionService(user)
    user_service = FakeUserService([user])
    
    with client_factory(session_service, user_service) as client:
        response = client.get(
            "/api/v1/users/search",
            params={"q": "test"},
            headers={"Authorization": "Bearer valid-token"}
        )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "users" in data
    assert len(data["users"]) == 1
    user_data = data["users"][0]
    assert user_data["username"] == "testuser"
    assert user_data["telegram_id"] == 123
    assert "photo_url" in user_data
    # Verify extra fields are NOT present
    assert "created_at" not in user_data
    assert "last_login_at" not in user_data
    assert "first_name" not in user_data


def test_search_users_min_length(client_factory):
    user = _sample_user()
    session_service = FakeSessionService(user)
    user_service = FakeUserService([])
    
    with client_factory(session_service, user_service) as client:
        response = client.get(
            "/api/v1/users/search",
            params={"q": "te"},
            headers={"Authorization": "Bearer valid-token"}
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    # FastAPI returns 400 VALIDATION_ERROR due to exception handler override in main.py
    assert response.json()["message"] == ErrorCode.VALIDATION_ERROR


def test_search_users_max_length(client_factory):
    user = _sample_user()
    session_service = FakeSessionService(user)
    user_service = FakeUserService([])
    
    with client_factory(session_service, user_service) as client:
        response = client.get(
            "/api/v1/users/search",
            params={"q": "a" * 65},
            headers={"Authorization": "Bearer valid-token"}
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["message"] == ErrorCode.VALIDATION_ERROR


def test_search_users_unauthorized(client_factory):
    user = _sample_user()
    session_service = FakeSessionService(user)
    user_service = FakeUserService([])
    
    with client_factory(session_service, user_service) as client:
        response = client.get(
            "/api/v1/users/search",
            params={"q": "test"}
        )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["message"] == ErrorCode.SESSION_MISSING


def test_search_users_limit(client_factory):
    user = _sample_user()
    session_service = FakeSessionService(user)
    user_service = FakeUserService([user] * 10)
    
    with client_factory(session_service, user_service) as client:
        response = client.get(
            "/api/v1/users/search",
            params={"q": "test", "limit": 5},
            headers={"Authorization": "Bearer valid-token"}
        )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data["users"]) == 5
