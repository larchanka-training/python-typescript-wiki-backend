"""Service for space-related business logic."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID
from datetime import datetime, timedelta, timezone

if TYPE_CHECKING:
    from app.repositories.spaces import SpaceRepository


class SpaceService:
    """Service for space-related operations."""

    def __init__(self, space_repository: SpaceRepository) -> None:
        self._space_repository = space_repository

    async def get_space(self, space_id: UUID, user) -> dict:
        """Return space info applying visibility rules for soft-deleted spaces.

        - If not deleted: visible to everyone.
        - If deleted and within 7 days: visible to owner and superadmin; include `deleted` flag.
        - If delete_scheduled_at passed: visible only to superadmin.
        """
        row = await self._space_repository.get_space_by_id(space_id)
        if row is None:
            raise ValueError("not found")

        now = datetime.now(timezone.utc)
        deleted = row["deleted_at"] is not None
        delete_scheduled = row["delete_scheduled_at"]

        # If not deleted — everyone can see
        if not deleted:
            return {"id": row["id"], "name": row["name"], "deleted": False}

        # If superadmin — always visible with deleted flag (regardless of time)
        if user.permission == "admin":
            return {
                "id": row["id"],
                "name": row["name"],
                "deleted": True,
                "deleted_at": row["deleted_at"],
                "delete_scheduled_at": delete_scheduled,
            }

        # If still within grace period, allow owner to see with deleted flag
        if delete_scheduled is not None and now < delete_scheduled:
            role = await self._space_repository.get_membership_role(space_id, user.id)
            if role == "owner":
                return {"id": row["id"], "name": row["name"], "deleted": True}

        # Otherwise not visible
        raise PermissionError("not found")

    async def create_space(self, name: str, user_id: int) -> UUID:
        """Create a new space for the user.

        Args:
            name: The name of the space.
            user_id: The ID of the user who will be the owner.

        Returns:
            UUID of the created space.
        """
        return await self._space_repository.create_space(name, user_id)

    async def delete_space(self, space_id: UUID, user) -> None:
        """Soft-delete a space: only owner or superadmin allowed.

        Marks `deleted_at` and schedules final hide after 7 days.
        """
        # Fetch space
        row = await self._space_repository.get_space_by_id(space_id)
        if row is None:
            raise ValueError("not found")

        # Superadmin bypass
        if user.permission == "admin":
            is_allowed = True
        else:
            # Check ownership
            role = await self._space_repository.get_membership_role(space_id, user.id)
            is_allowed = role == "owner"

        if not is_allowed:
            raise PermissionError("forbidden")

        now = datetime.now(timezone.utc)
        delete_after = now + timedelta(days=7)
        await self._space_repository.mark_deleted(space_id, now, delete_after)
