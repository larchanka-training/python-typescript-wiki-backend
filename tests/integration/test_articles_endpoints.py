"""Integration-style tests for /articles endpoints."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import FastAPI, status
from fastapi.testclient import TestClient
import pytest

from app.api.deps import get_article_service, get_session_service
from app.core.errors import ErrorCode
from app.main import app
from app.services.models import SessionData, UserProfile

SESSION_TOKEN = "session-token"  # noqa: S105
ARTICLE_ID = uuid4()
VERSION_ID = uuid4()


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


class FakeArticleService:
    """Test double for ArticleService."""

    def __init__(self, article_id: UUID, version_id: UUID) -> None:
        self._article_id = article_id
        self._version_id = version_id

    async def create_article(self, space_id: UUID, title: str, content: str, user_id: int) -> UUID:
        _ = space_id, title, content, user_id
        return self._article_id

    async def get_article_versions(self, article_id: UUID, user_id: int) -> list[dict]:
        _ = article_id, user_id
        now = datetime.now(timezone.utc)
        return [
            {
                "id": self._version_id,
                "article_id": article_id,
                "version_number": 1,
                "title": "Test Article",
                "content": "# Test Content",
                "author_id": 1,
                "created_at": now,
            }
        ]

    async def get_article_version(self, version_id: UUID, user_id: int) -> dict:
        _ = version_id, user_id
        now = datetime.now(timezone.utc)
        return {
            "id": self._version_id,
            "article_id": ARTICLE_ID,
            "version_number": 1,
            "title": "Test Article",
            "content": "# Test Content",
            "author_id": 1,
            "created_at": now,
        }


@pytest.fixture
def client_factory() -> Callable[[object, object], TestClient]:
    """Build a TestClient with service dependency overrides."""
    original_lifespan = app.router.lifespan_context

    def _factory(session_service: object, article_service: object) -> TestClient:
        app.dependency_overrides[get_session_service] = lambda: session_service
        app.dependency_overrides[get_article_service] = lambda: article_service
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


def test_create_article_success_returns_201(client_factory: Callable[[object, object], TestClient]) -> None:
    session_service = FakeSessionService(_sample_session_data())
    article_service = FakeArticleService(ARTICLE_ID, VERSION_ID)
    space_id = uuid4()

    with client_factory(session_service, article_service) as client:
        response = client.post(
            f"/api/v1/spaces/{space_id}/articles",
            json={"title": "New Article", "content": "# Content"},
            headers={"Authorization": f"Bearer {SESSION_TOKEN}"}
        )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["id"] == str(ARTICLE_ID)


def test_create_article_empty_title_returns_400(client_factory: Callable[[object, object], TestClient]) -> None:
    session_service = FakeSessionService(_sample_session_data())
    article_service = FakeArticleService(ARTICLE_ID, VERSION_ID)
    space_id = uuid4()

    with client_factory(session_service, article_service) as client:
        response = client.post(
            f"/api/v1/spaces/{space_id}/articles",
            json={"title": "", "content": "# Content"},
            headers={"Authorization": f"Bearer {SESSION_TOKEN}"}
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["message"] == ErrorCode.VALIDATION_ERROR


def test_create_article_missing_session_returns_401(client_factory: Callable[[object, object], TestClient]) -> None:
    session_service = FakeSessionService(_sample_session_data())
    article_service = FakeArticleService(ARTICLE_ID, VERSION_ID)
    space_id = uuid4()

    with client_factory(session_service, article_service) as client:
        response = client.post(
            f"/api/v1/spaces/{space_id}/articles",
            json={"title": "New Article", "content": "# Content"}
        )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["message"] == ErrorCode.SESSION_MISSING


def test_get_article_versions_success_returns_200(client_factory: Callable[[object, object], TestClient]) -> None:
    session_service = FakeSessionService(_sample_session_data())
    article_service = FakeArticleService(ARTICLE_ID, VERSION_ID)

    with client_factory(session_service, article_service) as client:
        response = client.get(
            f"/api/v1/articles/{ARTICLE_ID}/versions",
            headers={"Authorization": f"Bearer {SESSION_TOKEN}"}
        )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(VERSION_ID)
    assert data[0]["title"] == "Test Article"


def test_get_article_version_success_returns_200(client_factory: Callable[[object, object], TestClient]) -> None:
    session_service = FakeSessionService(_sample_session_data())
    article_service = FakeArticleService(ARTICLE_ID, VERSION_ID)

    with client_factory(session_service, article_service) as client:
        response = client.get(
            f"/api/v1/article-versions/{VERSION_ID}",
            headers={"Authorization": f"Bearer {SESSION_TOKEN}"}
        )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == str(VERSION_ID)
    assert data["title"] == "Test Article"