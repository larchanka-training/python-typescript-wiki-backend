"""Integration-style tests for /session endpoints."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, status
from fastapi.testclient import TestClient
import pytest

from app.api.deps import get_session_service
from app.core.errors import AppError, ErrorCode
from app.main import app
from app.services.models import SessionData, UserProfile

SESSION_TOKEN = "session-token"  # noqa: S105


@asynccontextmanager
async def _no_lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Disable lifespan to avoid DB setup during tests."""
    yield


class FakeSessionService:
    """Test double for SessionService returning a fixed session."""

    def __init__(self, data: SessionData) -> None:
        self._data = data

    async def create_session(self, _token: str, trace_id: str) -> SessionData:
        _ = trace_id
        return self._data

    async def get_session(self, _token: str, trace_id: str) -> SessionData:
        _ = trace_id
        return self._data

    async def refresh_session(self, _token: str, trace_id: str) -> SessionData:
        _ = trace_id
        return self._data

    async def revoke_session(self, _token: str, trace_id: str) -> None:
        _ = trace_id


class FakeSessionServiceError:
    """Test double for SessionService that raises a predefined AppError."""

    def __init__(self, error: AppError) -> None:
        self._error = error

    async def create_session(self, _token: str, trace_id: str) -> SessionData:
        _ = trace_id
        raise self._error

    async def get_session(self, _token: str, trace_id: str) -> SessionData:
        _ = trace_id
        raise self._error

    async def refresh_session(self, _token: str, trace_id: str) -> SessionData:
        _ = trace_id
        raise self._error

    async def revoke_session(self, _token: str, trace_id: str) -> None:
        _ = trace_id
        raise self._error


@pytest.fixture
def client_factory() -> Callable[[object], TestClient]:
    """Build a TestClient with SessionService dependency override."""
    original_lifespan = app.router.lifespan_context

    def _factory(service: object) -> TestClient:
        app.dependency_overrides[get_session_service] = lambda: service
        app.router.lifespan_context = _no_lifespan
        return TestClient(app)

    yield _factory
    app.dependency_overrides.clear()
    app.router.lifespan_context = original_lifespan


def _sample_data() -> SessionData:
    now = datetime.now(timezone.utc)
    user = UserProfile(
        id=1,
        telegram_id=123456,
        username="user",
        first_name=None,
        last_name=None,
        photo_url=None,
        permission=None,
        created_at=now,
        last_login_at=now,
    )
    return SessionData(user=user, expires_at=now, session_token=SESSION_TOKEN)


def test_create_session_success_returns_200(client_factory: Callable[[object], TestClient]) -> None:
    service = FakeSessionService(_sample_data())
    with client_factory(service) as client:
        response = client.post("/session", json={"token": "oauth-token"})

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["authenticated"] is True
    assert response.json()["session_token"] == SESSION_TOKEN


def test_create_session_missing_body_returns_400(client_factory: Callable[[object], TestClient]) -> None:
    service = FakeSessionService(_sample_data())
    with client_factory(service) as client:
        response = client.post("/session")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["message"] == ErrorCode.VALIDATION_ERROR


def test_create_session_empty_token_returns_400(client_factory: Callable[[object], TestClient]) -> None:
    service = FakeSessionService(_sample_data())
    with client_factory(service) as client:
        response = client.post("/session", json={"token": "   "})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["message"] == ErrorCode.VALIDATION_ERROR


def test_create_session_invalid_returns_401(client_factory: Callable[[object], TestClient]) -> None:
    error = AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.OAUTH_CODE_INVALID)
    service = FakeSessionServiceError(error)
    with client_factory(service) as client:
        response = client.post("/session", json={"token": "bad-token"})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["message"] == ErrorCode.OAUTH_CODE_INVALID


def test_get_session_missing_header_returns_401(client_factory: Callable[[object], TestClient]) -> None:
    service = FakeSessionService(_sample_data())
    with client_factory(service) as client:
        response = client.get("/session")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["message"] == ErrorCode.SESSION_MISSING


def test_get_session_invalid_header_returns_400(client_factory: Callable[[object], TestClient]) -> None:
    service = FakeSessionService(_sample_data())
    with client_factory(service) as client:
        response = client.get("/session", headers={"Authorization": "Token abc"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["message"] == ErrorCode.VALIDATION_ERROR


def test_get_session_success_returns_200(client_factory: Callable[[object], TestClient]) -> None:
    service = FakeSessionService(_sample_data())
    with client_factory(service) as client:
        response = client.get("/session", headers={"Authorization": f"Bearer {SESSION_TOKEN}"})

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["authenticated"] is True


def test_get_session_expired_returns_401(client_factory: Callable[[object], TestClient]) -> None:
    error = AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.SESSION_EXPIRED)
    service = FakeSessionServiceError(error)
    with client_factory(service) as client:
        response = client.get("/session", headers={"Authorization": f"Bearer {SESSION_TOKEN}"})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["message"] == ErrorCode.SESSION_EXPIRED


def test_refresh_session_success_returns_200(client_factory: Callable[[object], TestClient]) -> None:
    service = FakeSessionService(_sample_data())
    with client_factory(service) as client:
        response = client.post("/session/refresh", headers={"Authorization": f"Bearer {SESSION_TOKEN}"})

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["authenticated"] is True


def test_refresh_session_missing_header_returns_401(client_factory: Callable[[object], TestClient]) -> None:
    service = FakeSessionService(_sample_data())
    with client_factory(service) as client:
        response = client.post("/session/refresh")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["message"] == ErrorCode.SESSION_MISSING


def test_delete_session_success_returns_200(client_factory: Callable[[object], TestClient]) -> None:
    service = FakeSessionService(_sample_data())
    with client_factory(service) as client:
        response = client.delete("/session", headers={"Authorization": f"Bearer {SESSION_TOKEN}"})

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["authenticated"] is False


def test_delete_session_missing_header_returns_401(client_factory: Callable[[object], TestClient]) -> None:
    service = FakeSessionService(_sample_data())
    with client_factory(service) as client:
        response = client.delete("/session")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["message"] == ErrorCode.SESSION_MISSING
