"""Integration-style tests for /spaces endpoints."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, status
from fastapi.testclient import TestClient
import pytest

from app.api.deps import get_session_service, get_space_service
from app.core.errors import ErrorCode
from app.main import app
from app.services.models import SessionData, UserProfile

SESSION_TOKEN = "session-token"  # noqa: S105
SPACE_ID = uuid4()


@asynccontextmanager
async def _no_lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Disable lifespan to avoid DB setup during tests."""
    yield


class FakeSessionService:
    """Test double for SessionService returning a fixed session."""

    def __init__(self, data: SessionData) -> None:
        self._data = data

    async def get_session(self, _token: str, trace_id: str) -> SessionData:
        _ = trace_id
        return self._data


class FakeSpaceService:
    """Test double for SpaceService returning a fixed space ID."""

    def __init__(self, space_id: UUID) -> None:
        self._space_id = space_id

    async def create_space(self, name: str, user_id: int) -> UUID:
        _ = name
        _ = user_id
        return self._space_id


@pytest.fixture
def client_factory() -> Callable[[object, object], TestClient]:
    """Build a TestClient with service dependency overrides."""
    original_lifespan = app.router.lifespan_context

    def _factory(session_service: object, space_service: object) -> TestClient:
        app.dependency_overrides[get_session_service] = lambda: session_service
        app.dependency_overrides[get_space_service] = lambda: space_service
        app.router.lifespan_context = _no_lifespan
        return TestClient(app)

    yield _factory
    app.dependency_overrides.clear()
    app.router.lifespan_context = original_lifespan


def _sample_session_data() -> SessionData:
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


def test_create_space_success_returns_201(client_factory: Callable[[object, object], TestClient]) -> None:
    session_service = FakeSessionService(_sample_session_data())
    space_service = FakeSpaceService(SPACE_ID)
    
    with client_factory(session_service, space_service) as client:
        response = client.post(
            "/spaces", 
            json={"name": "New Space"},
            headers={"Authorization": f"Bearer {SESSION_TOKEN}"}
        )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["id"] == str(SPACE_ID)


def test_create_space_missing_name_returns_400(client_factory: Callable[[object, object], TestClient]) -> None:
    session_service = FakeSessionService(_sample_session_data())
    space_service = FakeSpaceService(SPACE_ID)
    
    with client_factory(session_service, space_service) as client:
        response = client.post(
            "/spaces", 
            json={"name": "   "},
            headers={"Authorization": f"Bearer {SESSION_TOKEN}"}
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["message"] == ErrorCode.VALIDATION_ERROR


def test_create_space_missing_session_returns_401(client_factory: Callable[[object, object], TestClient]) -> None:
    session_service = FakeSessionService(_sample_session_data())
    space_service = FakeSpaceService(SPACE_ID)
    
    with client_factory(session_service, space_service) as client:
        response = client.post(
            "/spaces", 
            json={"name": "New Space"}
        )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["message"] == ErrorCode.SESSION_MISSING
