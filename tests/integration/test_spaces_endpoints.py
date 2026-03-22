"""Integration-style tests for /spaces endpoints."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

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

    async def get_spaces(self, user_id: int) -> list[dict]:
        _ = user_id
        now = datetime.now(timezone.utc)

        owner_id = uuid4()
        recent_deleted_id = uuid4()
        recent_deleted_at = (now - timedelta(days=1)).isoformat()

        return [
            {"id": owner_id, "name": "Owner Space", "role": "owner", "deleted_at": None, "is_deleted": False},
            {
                "id": recent_deleted_id,
                "name": "Recently Deleted",
                "role": "member",
                "deleted_at": recent_deleted_at,
                "is_deleted": True,
            },
        ]


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
            "/api/v1/spaces", json={"name": "New Space"}, headers={"Authorization": f"Bearer {SESSION_TOKEN}"}
        )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["id"] == str(SPACE_ID)


def test_create_space_missing_name_returns_400(client_factory: Callable[[object, object], TestClient]) -> None:
    session_service = FakeSessionService(_sample_session_data())
    space_service = FakeSpaceService(SPACE_ID)

    with client_factory(session_service, space_service) as client:
        response = client.post(
            "/api/v1/spaces", json={"name": "   "}, headers={"Authorization": f"Bearer {SESSION_TOKEN}"}
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["message"] == ErrorCode.VALIDATION_ERROR


def test_create_space_missing_session_returns_401(client_factory: Callable[[object, object], TestClient]) -> None:
    session_service = FakeSessionService(_sample_session_data())
    space_service = FakeSpaceService(SPACE_ID)

    with client_factory(session_service, space_service) as client:
        response = client.post("/api/v1/spaces", json={"name": "New Space"})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["message"] == ErrorCode.SESSION_MISSING


def test_create_space_invalid_auth_header_returns_400(
    client_factory: Callable[[object, object], TestClient],
) -> None:
    """Test that invalid authorization header format returns 400."""
    session_service = FakeSessionService(_sample_session_data())
    space_service = FakeSpaceService(SPACE_ID)

    with client_factory(session_service, space_service) as client:
        response = client.post(
            "/spaces", json={"name": "New Space"}, headers={"Authorization": "InvalidToken"}
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["message"] == ErrorCode.VALIDATION_ERROR


def test_create_space_empty_auth_header_returns_401(client_factory: Callable[[object, object], TestClient]) -> None:
    """Test that empty authorization header returns 401."""
    session_service = FakeSessionService(_sample_session_data())
    space_service = FakeSpaceService(SPACE_ID)

    with client_factory(session_service, space_service) as client:
        response = client.post(
            "/spaces", json={"name": "New Space"}, headers={"Authorization": ""}
        )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["message"] == ErrorCode.SESSION_MISSING


def test_create_space_bearer_no_token_returns_400(client_factory: Callable[[object, object], TestClient]) -> None:
    """Test that Bearer without token returns 400."""
    session_service = FakeSessionService(_sample_session_data())
    space_service = FakeSpaceService(SPACE_ID)

    with client_factory(session_service, space_service) as client:
        response = client.post(
            "/spaces", json={"name": "New Space"}, headers={"Authorization": "Bearer "}
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["message"] == ErrorCode.VALIDATION_ERROR


def test_create_space_name_too_long_returns_400(client_factory: Callable[[object, object], TestClient]) -> None:
    """Test that space name exceeding 255 chars returns 400."""
    session_service = FakeSessionService(_sample_session_data())
    space_service = FakeSpaceService(SPACE_ID)
    long_name = "x" * 256

    with client_factory(session_service, space_service) as client:
        response = client.post(
            "/spaces",
            json={"name": long_name},
            headers={"Authorization": f"Bearer {SESSION_TOKEN}"},
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_space_missing_name_field_returns_422(client_factory: Callable[[object, object], TestClient]) -> None:
    """Test that missing name field returns 400 (validation error from Pydantic via route)."""
    session_service = FakeSessionService(_sample_session_data())
    space_service = FakeSpaceService(SPACE_ID)

    with client_factory(session_service, space_service) as client:
        response = client.post(
            "/spaces", json={}, headers={"Authorization": f"Bearer {SESSION_TOKEN}"}
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_space_session_expired_returns_401(client_factory: Callable[[object, object], TestClient]) -> None:
    """Test that expired session returns 401."""
    class FakeExpiredSessionService:
        async def get_session(self, _token: str, trace_id: str) -> None:
            _ = trace_id
            from app.core.errors import AppError
            raise AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.SESSION_EXPIRED)

    session_service = FakeExpiredSessionService()
    space_service = FakeSpaceService(SPACE_ID)

    with client_factory(session_service, space_service) as client:
        response = client.post(
            "/spaces", json={"name": "New Space"}, headers={"Authorization": f"Bearer {SESSION_TOKEN}"}
        )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["message"] == ErrorCode.SESSION_EXPIRED


def test_create_space_with_special_chars_returns_201(client_factory: Callable[[object, object], TestClient]) -> None:
    """Test that space name with special characters is accepted."""
    session_service = FakeSessionService(_sample_session_data())
    space_service = FakeSpaceService(SPACE_ID)
    special_name = "Test Space 📚 #123 @2025!"

    with client_factory(session_service, space_service) as client:
        response = client.post(
            "/spaces",
            json={"name": special_name},
            headers={"Authorization": f"Bearer {SESSION_TOKEN}"},
        )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["id"] == str(SPACE_ID)


def test_create_space_with_unicode_returns_201(client_factory: Callable[[object, object], TestClient]) -> None:
    """Test that space name with unicode characters is accepted."""
    session_service = FakeSessionService(_sample_session_data())
    space_service = FakeSpaceService(SPACE_ID)
    unicode_name = "Пространство 中文 العربية"

    with client_factory(session_service, space_service) as client:
        response = client.post(
            "/spaces",
            json={"name": unicode_name},
            headers={"Authorization": f"Bearer {SESSION_TOKEN}"},
        )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["id"] == str(SPACE_ID)


def test_create_space_single_char_name_returns_201(client_factory: Callable[[object, object], TestClient]) -> None:
    """Test that single character space name is accepted."""
    session_service = FakeSessionService(_sample_session_data())
    space_service = FakeSpaceService(SPACE_ID)

    with client_factory(session_service, space_service) as client:
        response = client.post(
            "/spaces",
            json={"name": "A"},
            headers={"Authorization": f"Bearer {SESSION_TOKEN}"},
        )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["id"] == str(SPACE_ID)


def test_create_space_max_length_name_returns_201(client_factory: Callable[[object, object], TestClient]) -> None:
    """Test that 255-character space name is accepted."""
    session_service = FakeSessionService(_sample_session_data())
    space_service = FakeSpaceService(SPACE_ID)
    max_name = "x" * 255

    with client_factory(session_service, space_service) as client:
        response = client.post(
            "/spaces",
            json={"name": max_name},
            headers={"Authorization": f"Bearer {SESSION_TOKEN}"},
        )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["id"] == str(SPACE_ID)
