"""UserService handles user-related business logic."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.repositories.users import UserRepository
    from app.services.models import UserProfile


class UserService:
    """UserService provides methods to interact with users."""

    def __init__(self, user_repository: UserRepository) -> None:
        self._user_repository = user_repository

    async def search_users(self, query: str, limit: int) -> list[UserProfile]:
        """Search users by username."""
        return await self._user_repository.search_by_username(query, limit)
