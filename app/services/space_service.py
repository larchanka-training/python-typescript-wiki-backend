"""Service for space-related business logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

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

    async def restore_space(self, space_id: UUID, user) -> None:
        """Restore a soft-deleted space: only owner or superadmin allowed.

        The space must be deleted and still visible to the user (within 7 days for owner).
        """
        # Fetch space
        row = await self._space_repository.get_space_by_id(space_id)
        if row is None:
            raise ValueError("not found")

        # Check if space is deleted
        if row["deleted_at"] is None:
            raise ValueError("not deleted")

        now = datetime.now(timezone.utc)
        delete_scheduled = row["delete_scheduled_at"]

        # Superadmin can always restore
        if user.permission == "admin":
            is_allowed = True
        else:
            # Check if owner and within grace period
            role = await self._space_repository.get_membership_role(space_id, user.id)
            is_allowed = role == "owner" and delete_scheduled is not None and now < delete_scheduled

        if not is_allowed:
            raise PermissionError("forbidden")

        # Reset deletion flags
        await self._space_repository.reset_deleted(space_id)

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

    async def get_spaces(self, user_id: int) -> list[dict]:
        """Get all spaces for the user.

        Args:
            user_id: The ID of the user.

        Returns:
            List of spaces the user is a member of.
        """
        spaces = await self._space_repository.get_spaces(user_id)

        return self.format_spaces(spaces)

    @staticmethod
    def format_spaces(spaces: list[dict]) -> list[dict]:
        """Filter, format and sort spaces for presentation.

        - Excludes spaces deleted more than 7 days ago.
        - Converts string `deleted_at` to datetime when needed.
        - Maps repository rows to output dicts and sorts owners first.
        """
        now = datetime.now(timezone.utc)

        filtered_spaces: list[dict] = []
        for space in spaces:
            deleted_at = space.get("deleted_at")

            if deleted_at and now - deleted_at.astimezone(timezone.utc) > timedelta(days=7):
                continue

            filtered_spaces.append(
                {
                    "id": space["id"],
                    "name": space["name"],
                    "role": space["role"],
                    "is_deleted": deleted_at is not None,
                    "deleted_at": deleted_at,
                }
            )

        filtered_spaces.sort(key=lambda x: (x["role"] != "owner", x["id"]))
        return filtered_spaces
