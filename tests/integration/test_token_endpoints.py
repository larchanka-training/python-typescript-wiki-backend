"""Integration-style tests for /token with real token validation."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, status
from fastapi.testclient import TestClient
import pytest

from app.api.deps import get_auth_service
from app.core.errors import AppError, ErrorCode
from app.db import get_connection
from app.main import app
from app.services.models import UserProfile


@asynccontextmanager
async def _no_lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Disable lifespan to avoid DB/http client setup during tests."""
    yield


def _sample_test_user() -> UserProfile:
    """Create a sample test user response."""
    now = datetime.now(timezone.utc)
    return UserProfile(
        id=9999999,
        telegram_id=9999999,
        username="test_user",
        first_name="Test",
        last_name="User",
        photo_url=None,
        permission=None,
        created_at=now,
        last_login_at=now,
    )


@pytest.fixture
def client_factory() -> Callable[..., TestClient]:
    """Build a TestClient using real token validation logic.
    
    Disables lifespan and overrides get_connection since test tokens
    don't actually require database access.
    """
    original_lifespan = app.router.lifespan_context

    def _factory() -> TestClient:
        app.router.lifespan_context = _no_lifespan
        # Override get_connection to avoid DB pool requirement
        # (test tokens never actually use the connection)
        app.dependency_overrides[get_connection] = lambda: None
        return TestClient(app)

    yield _factory
    app.dependency_overrides.clear()
    app.router.lifespan_context = original_lifespan


def test_verity_test_token_returns_200(client_factory: Callable) -> None:
    """Valid test token returns 200 using real TokenService validation."""
    client = client_factory()
    response = client.post(
        "/token",
        json={"token": "32u5g34u45gi243u4g23iu"},
    )

    assert response.status_code == status.HTTP_200_OK


def test_verity_test_token_returns_errors(client_factory: Callable) -> None:
    """Invalid token returns 401 using real TokenService validation."""
    client = client_factory()
    response = client.post(
        "/token",
        json={"token": "RandomTestToken12345"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["message"] == ErrorCode.OAUTH_CODE_INVALID