"""Service for space-related business logic."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from app.repositories.spaces import SpaceRepository


class SpaceService:
    """Service for space-related operations."""

    def __init__(self, space_repository: SpaceRepository) -> None:
        self._space_repository = space_repository

    async def create_space(self, name: str, user_id: int) -> UUID:
        """Create a new space for the user.

        Args:
            name: The name of the space.
            user_id: The ID of the user who will be the owner.

        Returns:
            UUID of the created space.
        """
        return await self._space_repository.create_space(name, user_id)
