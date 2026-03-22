"""Integration-style tests for /articles endpoints."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest import TestCase
from uuid import UUID, uuid4

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from app.api.deps import get_article_service, get_session_service
from app.core.errors import ErrorCode
from app.main import app
from app.repositories.articles import ConflictError
from app.services.models import SessionData, UserProfile

SESSION_TOKEN = "session-token"  # noqa: S105
ARTICLE_ID = uuid4()
VERSION_ID = uuid4()
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


class FakeArticleService:
    """Test double for ArticleService (new API)."""

    def __init__(self, article_id: UUID, version_id: UUID) -> None:
        self._article_id = article_id
        self._version_id = version_id

    async def create_article(
        self,
        space_id: UUID,
        title: str,
        content: str,
        user_id: int,
        *,
        show_toc: bool = False,
        parent_id: UUID | None = None,
        position: int = 0,
    ) -> UUID:
        _ = space_id, title, content, user_id, show_toc, parent_id, position
        return self._article_id

    async def list_articles(
        self, space_id: UUID, user_id: int, user_permission: str | None, parent_id: UUID | None = None, filter_by_parent: bool = False
    ) -> list[dict]:
        _ = space_id, user_id, user_permission, parent_id, filter_by_parent
        now = datetime.now(timezone.utc)
        return [
            {
                "id": self._article_id,
                "space_id": space_id,
                "title": "Test Article",
                "owner_id": 1,
                "parent_id": None,
                "position": 0,
                "created_at": now,
                "updated_at": now,
                "is_locked": False,
                "permissions": {"can_edit": True, "can_delete": False, "can_lock": False},
            }
        ]

    async def get_recent_articles(self, user_id: int, limit: int = 10) -> list[dict]:
        _ = user_id, limit
        now = datetime.now(timezone.utc)
        return [
            {
                "id": uuid4(),
                "title": "Recent Article 1",
                "space_id": uuid4(),
                "space_name": "Recent Space",
                "owner_id": 1,
                "parent_id": None,
                "position": 0,
                "created_at": now,
                "updated_at": now,
                "is_locked": False,
                "permissions": {"can_edit": True, "can_delete": False, "can_lock": False},
            }
        ]

    async def search_articles(self, user_id: int, query: str, limit: int = 20) -> list[dict]:
        _ = user_id, query, limit
        now = datetime.now(timezone.utc)
        return [
            {
                "id": uuid4(),
                "title": "Search Result",
                "space_id": uuid4(),
                "space_name": "Search Space",
                "owner_id": 1,
                "parent_id": None,
                "position": 0,
                "created_at": now,
                "updated_at": now,
                "is_locked": False,
                "permissions": {"can_edit": True, "can_delete": False, "can_lock": False},
            }
        ]

    async def get_article_path(self, space_id: UUID, article_id: UUID, user_id: int, user_permission: str | None) -> list[dict]:
        _ = space_id, article_id, user_id, user_permission
        now = datetime.now(timezone.utc)
        # Return path to root (only the article itself in this fake)
        return [
            {
                "id": self._article_id,
                "space_id": space_id,
                "title": "Test Article",
                "owner_id": 1,
                "parent_id": None,
                "position": 0,
                "created_at": now,
                "updated_at": now,
                "is_locked": False,
                "permissions": {"can_edit": True, "can_delete": False, "can_lock": False},
            }
        ]

    async def save_article_version(
        self,
        space_id: UUID,
        article_id: UUID,
        title: str,
        content: str,
        user_id: int,
        user_permission: str | None,
        *,
        show_toc: bool = False,
        content_format: str = "markdown",
        change_summary: str | None = None,
        base_version_number: int | None = None,
    ) -> UUID:
        _ = space_id, article_id, title, content, user_id, user_permission
        _ = show_toc, content_format, change_summary, base_version_number
        self._version_id = uuid4()
        return self._version_id

    async def lock_article(
        self, space_id: UUID, article_id: UUID, user_id: int, user_permission: str | None,
    ) -> None:
        _ = space_id, article_id, user_id, user_permission

    async def unlock_article(
        self, space_id: UUID, article_id: UUID, user_id: int, user_permission: str | None,
    ) -> None:
        _ = space_id, article_id, user_id, user_permission

    async def get_article_versions(
        self, space_id: UUID, article_id: UUID, user_id: int, user_permission: str | None,
    ) -> list[dict]:
        _ = space_id, article_id, user_id, user_permission
        now = datetime.now(timezone.utc)
        return [
            {
                "id": self._version_id,
                "article_id": article_id,
                "version_number": 1,
                "title": "Test Article",
                "content": "# Test Content",
                "author_id": 1,
                "show_toc": False,
                "content_format": "markdown",
                "change_summary": None,
                "created_at": now,
                "is_locked": False,
                "permissions": {"can_edit": True, "can_delete": False, "can_lock": False},
            }
        ]

    async def get_latest_article_version(
        self, space_id: UUID, article_id: UUID, user_id: int, user_permission: str | None,
    ) -> dict:
        _ = space_id, article_id, user_id, user_permission
        now = datetime.now(timezone.utc)
        return {
            "id": self._version_id,
            "article_id": article_id,
            "version_number": 1,
            "title": "Test Article",
            "content": "# Test Content",
            "author_id": 1,
            "show_toc": False,
            "content_format": "markdown",
            "change_summary": None,
            "created_at": now,
            "is_locked": False,
            "permissions": {"can_edit": True, "can_delete": False, "can_lock": False},
        }

    async def get_article_version_by_number(
        self, space_id: UUID, article_id: UUID, version_number: int, user_id: int, user_permission: str | None,
    ) -> dict:
        _ = space_id, article_id, user_id, user_permission
        now = datetime.now(timezone.utc)
        return {
            "id": self._version_id,
            "article_id": article_id,
            "version_number": version_number,
            "title": "Test Article",
            "content": "# Test Content",
            "author_id": 1,
            "show_toc": False,
            "content_format": "markdown",
            "change_summary": None,
            "created_at": now,
            "is_locked": False,
            "permissions": {"can_edit": True, "can_delete": False, "can_lock": False},
        }

    async def delete_article(
        self, space_id: UUID, article_id: UUID, user_id: int, user_permission: str | None,
    ) -> None:
        _ = space_id, article_id, user_id, user_permission


class TestArticlesEndpoints(TestCase):
    def setUp(self):
        self.original_lifespan = app.router.lifespan_context
        app.router.lifespan_context = _no_lifespan

    def tearDown(self):
        app.dependency_overrides.clear()
        app.router.lifespan_context = self.original_lifespan

    def _create_client(self, session_service, article_service):
        app.dependency_overrides[get_session_service] = lambda: session_service
        app.dependency_overrides[get_article_service] = lambda: article_service
        return TestClient(app)

    def _sample_session_data(self):
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

    # ── POST create ─────────────────────────────────────────────────

    def test_create_article_success_returns_201(self):
        session_service = FakeSessionService(self._sample_session_data())
        article_service = FakeArticleService(ARTICLE_ID, VERSION_ID)

        with self._create_client(session_service, article_service) as client:
            response = client.post(
                f"/api/v1/spaces/{SPACE_ID}/articles",
                json={"title": "New Article", "content": "# Content"},
                headers={"Authorization": f"Bearer {SESSION_TOKEN}"},
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["id"], str(ARTICLE_ID))

    def test_create_article_empty_title_returns_400(self):
        session_service = FakeSessionService(self._sample_session_data())
        article_service = FakeArticleService(ARTICLE_ID, VERSION_ID)

        with self._create_client(session_service, article_service) as client:
            response = client.post(
                f"/api/v1/spaces/{SPACE_ID}/articles",
                json={"title": "", "content": "# Content"},
                headers={"Authorization": f"Bearer {SESSION_TOKEN}"},
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["message"], ErrorCode.VALIDATION_ERROR)

    def test_create_article_missing_session_returns_401(self):
        session_service = FakeSessionService(self._sample_session_data())
        article_service = FakeArticleService(ARTICLE_ID, VERSION_ID)

        with self._create_client(session_service, article_service) as client:
            response = client.post(
                f"/api/v1/spaces/{SPACE_ID}/articles",
                json={"title": "New Article", "content": "# Content"},
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.json()["message"], ErrorCode.SESSION_MISSING)

    # ── GET list ────────────────────────────────────────────────────

    def test_list_articles_success_returns_200(self):
        session_service = FakeSessionService(self._sample_session_data())
        article_service = FakeArticleService(ARTICLE_ID, VERSION_ID)

        with self._create_client(session_service, article_service) as client:
            response = client.get(
                f"/api/v1/spaces/{SPACE_ID}/articles",
                headers={"Authorization": f"Bearer {SESSION_TOKEN}"},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("articles", data)
        self.assertEqual(len(data["articles"]), 1)

    # ── GET latest version ──────────────────────────────────────────

    def test_get_article_success_returns_200(self):
        session_service = FakeSessionService(self._sample_session_data())
        article_service = FakeArticleService(ARTICLE_ID, VERSION_ID)

        with self._create_client(session_service, article_service) as client:
            response = client.get(
                f"/api/v1/spaces/{SPACE_ID}/articles/{ARTICLE_ID}",
                headers={"Authorization": f"Bearer {SESSION_TOKEN}"},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["id"], str(VERSION_ID))
        self.assertEqual(data["title"], "Test Article")

    # ── GET recent articles ─────────────────────────────────────────

    def test_get_recent_articles_success_returns_200(self):
        session_service = FakeSessionService(self._sample_session_data())
        article_service = FakeArticleService(ARTICLE_ID, VERSION_ID)

        with self._create_client(session_service, article_service) as client:
            response = client.get(
                "/api/v1/articles/recent",
                headers={"Authorization": f"Bearer {SESSION_TOKEN}"},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIsInstance(data["articles"], list)
        self.assertEqual(len(data["articles"]), 1)
        self.assertIn("space_name", data["articles"][0])
        self.assertEqual(data["articles"][0]["title"], "Recent Article 1")

    def test_get_recent_articles_missing_session_returns_401(self):
        session_service = FakeSessionService(self._sample_session_data())
        article_service = FakeArticleService(ARTICLE_ID, VERSION_ID)

        with self._create_client(session_service, article_service) as client:
            response = client.get("/api/v1/articles/recent")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.json()["message"], ErrorCode.SESSION_MISSING)

    # ── GET search articles ─────────────────────────────────────────

    def test_search_articles_success_returns_200(self):
        session_service = FakeSessionService(self._sample_session_data())
        article_service = FakeArticleService(ARTICLE_ID, VERSION_ID)

        with self._create_client(session_service, article_service) as client:
            response = client.get(
                "/api/v1/articles/search?q=test",
                headers={"Authorization": f"Bearer {SESSION_TOKEN}"},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIsInstance(data["articles"], list)
        self.assertEqual(len(data["articles"]), 1)
        self.assertEqual(data["articles"][0]["title"], "Search Result")

    def test_search_articles_min_length_returns_400(self):
        session_service = FakeSessionService(self._sample_session_data())
        article_service = FakeArticleService(ARTICLE_ID, VERSION_ID)

        with self._create_client(session_service, article_service) as client:
            response = client.get(
                "/api/v1/articles/search?q=te",
                headers={"Authorization": f"Bearer {SESSION_TOKEN}"},
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["message"], ErrorCode.VALIDATION_ERROR)

    def test_search_articles_unauthorized_returns_401(self):
        session_service = FakeSessionService(self._sample_session_data())
        article_service = FakeArticleService(ARTICLE_ID, VERSION_ID)

        with self._create_client(session_service, article_service) as client:
            response = client.get(
                "/api/v1/articles/search?q=test",
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.json()["message"], ErrorCode.SESSION_MISSING)

    # ── PUT save new version ────────────────────────────────────────

    def test_save_article_version_returns_200(self):
        session_service = FakeSessionService(self._sample_session_data())
        article_service = FakeArticleService(ARTICLE_ID, VERSION_ID)

        with self._create_client(session_service, article_service) as client:
            response = client.put(
                f"/api/v1/spaces/{SPACE_ID}/articles/{ARTICLE_ID}",
                json={"title": "Updated Title", "content": "# Updated"},
                headers={"Authorization": f"Bearer {SESSION_TOKEN}"},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["title"], "Test Article")  # returns latest from fake

    # ── DELETE ──────────────────────────────────────────────────────

    def test_delete_article_success_returns_204(self):
        session_service = FakeSessionService(self._sample_session_data())
        article_service = FakeArticleService(ARTICLE_ID, VERSION_ID)

        with self._create_client(session_service, article_service) as client:
            response = client.delete(
                f"/api/v1/spaces/{SPACE_ID}/articles/{ARTICLE_ID}",
                headers={"Authorization": f"Bearer {SESSION_TOKEN}"},
            )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_article_missing_session_returns_401(self):
        session_service = FakeSessionService(self._sample_session_data())
        article_service = FakeArticleService(ARTICLE_ID, VERSION_ID)

        with self._create_client(session_service, article_service) as client:
            response = client.delete(
                f"/api/v1/spaces/{SPACE_ID}/articles/{ARTICLE_ID}",
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.json()["message"], ErrorCode.SESSION_MISSING)

    # ── GET versions ────────────────────────────────────────────────

    def test_get_article_versions_success_returns_200(self):
        session_service = FakeSessionService(self._sample_session_data())
        article_service = FakeArticleService(ARTICLE_ID, VERSION_ID)

        with self._create_client(session_service, article_service) as client:
            response = client.get(
                f"/api/v1/spaces/{SPACE_ID}/articles/{ARTICLE_ID}/versions",
                headers={"Authorization": f"Bearer {SESSION_TOKEN}"},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], str(VERSION_ID))

    # ── GET version by number ───────────────────────────────────────

    def test_get_article_version_by_number_returns_200(self):
        session_service = FakeSessionService(self._sample_session_data())
        article_service = FakeArticleService(ARTICLE_ID, VERSION_ID)

        with self._create_client(session_service, article_service) as client:
            response = client.get(
                f"/api/v1/spaces/{SPACE_ID}/articles/{ARTICLE_ID}/versions/1",
                headers={"Authorization": f"Bearer {SESSION_TOKEN}"},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["version_number"], 1)