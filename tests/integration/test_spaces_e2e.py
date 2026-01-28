"""End-to-end tests for spaces functionality (complete workflows)."""

from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, status
from fastapi.testclient import TestClient
import pytest

from app.api.deps import (
    get_session_service,
    get_space_service,
)
from app.core.errors import ErrorCode
from app.main import app
from app.services.models import SessionData, UserProfile


@asynccontextmanager
async def _no_lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Disable lifespan to avoid DB setup during tests."""
    yield


class FakeSessionService:
    """Test double for SessionService managing sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionData] = {}
        self._token_counter = 0

    async def create_session(
        self, user: UserProfile, trace_id: str
    ) -> SessionData:
        """Create a new session and return session data."""
        _ = trace_id
        self._token_counter += 1
        session_token = f"session-token-{self._token_counter}"
        now = datetime.now(timezone.utc)
        session_data = SessionData(
            user=user,
            expires_at=now,
            session_token=session_token,
        )
        self._sessions[session_token] = session_data
        return session_data

    async def get_session(self, token: str, trace_id: str) -> SessionData:
        """Get session by token."""
        _ = trace_id
        if token not in self._sessions:
            from app.core.errors import AppError
            raise AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.SESSION_MISSING)
        return self._sessions[token]

    async def refresh_session(self, token: str, trace_id: str) -> SessionData:
        """Refresh a session."""
        _ = trace_id
        if token not in self._sessions:
            from app.core.errors import AppError
            raise AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.SESSION_EXPIRED)
        return self._sessions[token]

    async def revoke_session(self, token: str, trace_id: str) -> None:
        """Revoke a session."""
        _ = trace_id
        if token in self._sessions:
            del self._sessions[token]


class FakeSpaceService:
    """Test double for SpaceService managing spaces."""

    def __init__(self) -> None:
        self._spaces: dict[str, dict] = {}
        self._space_counter = 0

    async def create_space(self, name: str, user_id: int) -> str:
        """Create a new space and return its UUID."""
        self._space_counter += 1
        space_id = str(uuid4())
        self._spaces[space_id] = {
            "id": space_id,
            "name": name,
            "user_id": user_id,
        }
        return space_id

    def get_space(self, space_id: str) -> dict | None:
        """Get space by ID."""
        return self._spaces.get(space_id)

    def get_user_spaces(self, user_id: int) -> list[dict]:
        """Get all spaces for a user."""
        return [s for s in self._spaces.values() if s["user_id"] == user_id]


def _sample_user() -> UserProfile:
    """Create a sample user for testing."""
    now = datetime.now(timezone.utc)
    return UserProfile(
        id=1,
        telegram_id=123456,
        username="test_user",
        first_name="Test",
        last_name="User",
        photo_url=None,
        permission=None,
        created_at=now,
        last_login_at=now,
    )


@pytest.fixture
def e2e_client_factory() -> Callable[[], tuple[TestClient, FakeSessionService, FakeSpaceService]]:
    """Build a TestClient with all services for E2E testing."""
    original_lifespan = app.router.lifespan_context

    def _factory() -> tuple[TestClient, FakeSessionService, FakeSpaceService]:
        session_service = FakeSessionService()
        space_service = FakeSpaceService()

        app.dependency_overrides[get_session_service] = lambda: session_service
        app.dependency_overrides[get_space_service] = lambda: space_service
        app.router.lifespan_context = _no_lifespan
        
        client = TestClient(app)
        return client, session_service, space_service

    yield _factory
    app.dependency_overrides.clear()
    app.router.lifespan_context = original_lifespan


class TestSpacesE2E:
    """End-to-end tests for spaces functionality."""

    def test_space_creation_with_valid_session(
        self, e2e_client_factory: Callable[[], tuple[TestClient, FakeSessionService, FakeSpaceService]]
    ) -> None:
        """Test space creation with a valid session token."""
        client, session_service, space_service = e2e_client_factory()
        user = _sample_user()

        # Create a session directly in the service
        session_data = SessionData(
            user=user,
            expires_at=datetime.now(timezone.utc),
            session_token="test-session-123",
        )
        session_service._sessions["test-session-123"] = session_data

        # Create space with valid session
        response = client.post(
            "/spaces",
            json={"name": "My First Space"},
            headers={"Authorization": "Bearer test-session-123"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["id"] is not None

    def test_multiple_spaces_creation_same_user(
        self, e2e_client_factory: Callable[[], tuple[TestClient, FakeSessionService, FakeSpaceService]]
    ) -> None:
        """Test that a user can create multiple spaces."""
        client, session_service, space_service = e2e_client_factory()
        user = _sample_user()

        # Create a session
        session_data = SessionData(
            user=user,
            expires_at=datetime.now(timezone.utc),
            session_token="test-session-123",
        )
        session_service._sessions["test-session-123"] = session_data

        # Create multiple spaces
        space_names = ["Documentation", "Design", "Development", "Testing"]
        space_ids = []

        for name in space_names:
            response = client.post(
                "/spaces",
                json={"name": name},
                headers={"Authorization": "Bearer test-session-123"},
            )
            assert response.status_code == status.HTTP_201_CREATED
            space_ids.append(response.json()["id"])

        # Verify all spaces exist and belong to user
        user_spaces = space_service.get_user_spaces(1)
        assert len(user_spaces) == len(space_names)
        
        for space in user_spaces:
            assert space["user_id"] == 1
            assert space["name"] in space_names

    def test_space_creation_requires_valid_session_token(
        self, e2e_client_factory: Callable[[], tuple[TestClient, FakeSessionService, FakeSpaceService]]
    ) -> None:
        """Test that creating space with invalid session token fails."""
        client, session_service, space_service = e2e_client_factory()

        # Try to create space with non-existent session token
        response = client.post(
            "/spaces",
            json={"name": "Unauthorized Space"},
            headers={"Authorization": "Bearer invalid-session-token"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["message"] == ErrorCode.SESSION_MISSING

    def test_space_creation_with_multiple_different_session_tokens(
        self, e2e_client_factory: Callable[[], tuple[TestClient, FakeSessionService, FakeSpaceService]]
    ) -> None:
        """Test that different session tokens work independently."""
        client, session_service, space_service = e2e_client_factory()
        user1 = _sample_user()
        user2 = UserProfile(
            id=2,
            telegram_id=654321,
            username="test_user_2",
            first_name="Test",
            last_name="User2",
            photo_url=None,
            permission=None,
            created_at=datetime.now(timezone.utc),
            last_login_at=datetime.now(timezone.utc),
        )

        # Create two sessions
        session_data1 = SessionData(
            user=user1,
            expires_at=datetime.now(timezone.utc),
            session_token="test-session-1",
        )
        session_data2 = SessionData(
            user=user2,
            expires_at=datetime.now(timezone.utc),
            session_token="test-session-2",
        )
        session_service._sessions["test-session-1"] = session_data1
        session_service._sessions["test-session-2"] = session_data2

        # Create space with session 1
        response1 = client.post(
            "/spaces",
            json={"name": "Space for User 1"},
            headers={"Authorization": "Bearer test-session-1"},
        )
        assert response1.status_code == status.HTTP_201_CREATED

        # Create space with session 2
        response2 = client.post(
            "/spaces",
            json={"name": "Space for User 2"},
            headers={"Authorization": "Bearer test-session-2"},
        )
        assert response2.status_code == status.HTTP_201_CREATED

        # Verify spaces belong to correct users
        user1_spaces = space_service.get_user_spaces(1)
        user2_spaces = space_service.get_user_spaces(2)
        assert len(user1_spaces) == 1
        assert len(user2_spaces) == 1
        assert user1_spaces[0]["name"] == "Space for User 1"
        assert user2_spaces[0]["name"] == "Space for User 2"

    def test_space_with_whitespace_only_name_returns_400(
        self, e2e_client_factory: Callable[[], tuple[TestClient, FakeSessionService, FakeSpaceService]]
    ) -> None:
        """Test that space names with only whitespace are rejected."""
        client, session_service, space_service = e2e_client_factory()
        user = _sample_user()

        # Create session
        session_data = SessionData(
            user=user,
            expires_at=datetime.now(timezone.utc),
            session_token="test-session-123",
        )
        session_service._sessions["test-session-123"] = session_data

        # Try to create space with whitespace-only name
        response = client.post(
            "/spaces",
            json={"name": "   \t\n  "},
            headers={"Authorization": "Bearer test-session-123"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["message"] == ErrorCode.VALIDATION_ERROR

    def test_multiple_invalid_requests_handled_correctly(
        self, e2e_client_factory: Callable[[], tuple[TestClient, FakeSessionService, FakeSpaceService]]
    ) -> None:
        """Test that multiple invalid requests are handled correctly."""
        client, session_service, space_service = e2e_client_factory()
        user = _sample_user()

        # Create session
        session_data = SessionData(
            user=user,
            expires_at=datetime.now(timezone.utc),
            session_token="test-session-123",
        )
        session_service._sessions["test-session-123"] = session_data

        # Test 1: Missing auth header
        r1 = client.post("/spaces", json={"name": "Test"})
        assert r1.status_code == status.HTTP_401_UNAUTHORIZED

        # Test 2: Invalid auth header
        r2 = client.post(
            "/spaces",
            json={"name": "Test"},
            headers={"Authorization": "InvalidFormat"},
        )
        assert r2.status_code == status.HTTP_400_BAD_REQUEST

        # Test 3: Empty name
        r3 = client.post(
            "/spaces",
            json={"name": ""},
            headers={"Authorization": "Bearer test-session-123"},
        )
        assert r3.status_code == status.HTTP_400_BAD_REQUEST

        # Test 4: Valid request should still work
        r4 = client.post(
            "/spaces",
            json={"name": "Valid Space"},
            headers={"Authorization": "Bearer test-session-123"},
        )
        assert r4.status_code == status.HTTP_201_CREATED

    def test_space_creation_concurrent_requests(
        self, e2e_client_factory: Callable[[], tuple[TestClient, FakeSessionService, FakeSpaceService]]
    ) -> None:
        """Test creating multiple spaces in sequence (simulating concurrent requests)."""
        client, session_service, space_service = e2e_client_factory()
        user = _sample_user()

        # Create session
        session_data = SessionData(
            user=user,
            expires_at=datetime.now(timezone.utc),
            session_token="test-session-123",
        )
        session_service._sessions["test-session-123"] = session_data

        # Create 5 spaces in sequence
        responses = []
        for i in range(5):
            response = client.post(
                "/spaces",
                json={"name": f"Space {i+1}"},
                headers={"Authorization": "Bearer test-session-123"},
            )
            responses.append(response)

        # All should succeed
        for response in responses:
            assert response.status_code == status.HTTP_201_CREATED
            assert response.json()["id"] is not None

        # Verify all spaces were created
        user_spaces = space_service.get_user_spaces(1)
        assert len(user_spaces) == 5

    def test_response_format_consistency(
        self, e2e_client_factory: Callable[[], tuple[TestClient, FakeSessionService, FakeSpaceService]]
    ) -> None:
        """Test that response format is consistent across requests."""
        client, session_service, space_service = e2e_client_factory()
        user = _sample_user()

        # Create session
        session_data = SessionData(
            user=user,
            expires_at=datetime.now(timezone.utc),
            session_token="test-session-123",
        )
        session_service._sessions["test-session-123"] = session_data

        # Create space
        response = client.post(
            "/spaces",
            json={"name": "Format Test Space"},
            headers={"Authorization": "Bearer test-session-123"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        # Verify response structure
        assert "id" in data
        assert len(data) == 1  # Only 'id' field
        
        # Verify ID is a valid UUID string format
        import uuid
        try:
            uuid.UUID(data["id"])
            uuid_valid = True
        except ValueError:
            uuid_valid = False
        assert uuid_valid
