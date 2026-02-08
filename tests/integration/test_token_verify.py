"""Integration-style tests for /token."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, status
from fastapi.testclient import TestClient
import pytest

from app.api.deps import get_auth_service
from app.core.errors import AppError, ErrorCode
from app.main import app
from app.services.models import UserProfile

TELEGRAM_ID = 123456


@asynccontextmanager
async def _no_lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Disable lifespan to avoid DB/http client setup during tests."""
    yield


class FakeAuthService:
    """Test double for AuthService returning a fixed user."""

    def __init__(self, user: UserProfile, *, created: bool) -> None:
        self._user = user
        self._created = created

    async def verify_token(self, _token: str, trace_id: str) -> tuple[UserProfile, bool]:
        _ = trace_id
        return self._user, self._created


class FakeAuthServiceError:
    """Test double for AuthService that raises a predefined AppError."""

    def __init__(self, error: AppError) -> None:
        self._error = error

    async def verify_token(self, _token: str, trace_id: str) -> None:
        _ = trace_id
        raise self._error


@pytest.fixture
def client_factory() -> Callable[[object], TestClient]:
    """Build a TestClient with AuthService dependency override."""
    original_lifespan = app.router.lifespan_context

    def _factory(service: object) -> TestClient:
        app.dependency_overrides[get_auth_service] = lambda: service
        app.router.lifespan_context = _no_lifespan
        return TestClient(app)

    yield _factory
    app.dependency_overrides.clear()
    app.router.lifespan_context = original_lifespan


def _sample_user() -> UserProfile:
    """Create a sample user response for success cases."""
    now = datetime.now(timezone.utc)
    return UserProfile(
        id=1,
        telegram_id=TELEGRAM_ID,
        username="user",
        first_name="First",
        last_name="Last",
        photo_url="https://example.com/photo.png",
        permission="admin",
        created_at=now,
        last_login_at=now,
    )


def test_verify_token_created_returns_200(client_factory: Callable[[object], TestClient]) -> None:
    """New user results in 200 and user payload."""
    service = FakeAuthService(_sample_user(), created=True)
    with client_factory(service) as client:
        response = client.post(
            "/api/v1/token",
            json={"token": "test-token"},
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["created"] is True
    assert response.json()["user"]["telegram_id"] == TELEGRAM_ID


def test_verify_token_existing_returns_200(client_factory: Callable[[object], TestClient]) -> None:
    """Existing user results in 200 and user payload."""
    service = FakeAuthService(_sample_user(), created=False)
    with client_factory(service) as client:
        response = client.post(
            "/api/v1/token",
            json={"token": "test-token"},
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["created"] is False
    assert response.json()["user"]["telegram_id"] == TELEGRAM_ID


def test_verify_token_missing_returns_400(client_factory: Callable[[object], TestClient]) -> None:
    """Missing token returns 400 + VALIDATION_ERROR."""
    service = FakeAuthService(_sample_user(), created=True)
    with client_factory(service) as client:
        response = client.post("/api/v1/token")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["message"] == ErrorCode.VALIDATION_ERROR
    assert response.json()["status"] == "error"
    assert response.json()["timestamp"]


def test_verify_token_empty_returns_400(client_factory: Callable[[object], TestClient]) -> None:
    """Blank token returns 400 + VALIDATION_ERROR."""
    service = FakeAuthService(_sample_user(), created=True)
    with client_factory(service) as client:
        response = client.post("/api/v1/token", json={"token": "   "})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["message"] == ErrorCode.VALIDATION_ERROR


def test_verify_token_invalid_returns_401(client_factory: Callable[[object], TestClient]) -> None:
    """Invalid token returns 401 + OAUTH_CODE_INVALID."""
    error = AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.OAUTH_CODE_INVALID)
    service = FakeAuthServiceError(error)
    with client_factory(service) as client:
        response = client.post(
            "/api/v1/token",
            json={"token": "test-token"},
        )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["message"] == ErrorCode.OAUTH_CODE_INVALID


def test_verify_token_internal_error_returns_500(client_factory: Callable[[object], TestClient]) -> None:
    """Internal error returns 500 + INTERNAL_ERROR."""
    error = AppError(status.HTTP_500_INTERNAL_SERVER_ERROR, ErrorCode.INTERNAL_ERROR)
    service = FakeAuthServiceError(error)
    with client_factory(service) as client:
        response = client.post(
            "/api/v1/token",
            json={"token": "test-token"},
        )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json()["message"] == ErrorCode.INTERNAL_ERROR
