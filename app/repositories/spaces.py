"""Repositories for spaces."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    import asyncpg


class SpaceRepository:
    """Repository for spaces (asyncpg)."""

    def __init__(self, connection: asyncpg.Connection) -> None:
        self._connection = connection

    async def create_space(self, name: str, owner_id: int) -> UUID:
        """Create a new space and add the owner membership in a transaction.

        Returns:
            UUID of the created space.
        """
        async with self._connection.transaction():
            # 1. Insert into spaces table
            space_id = await self._connection.fetchval(
                """
                INSERT INTO spaces (id, name)
                VALUES (gen_random_uuid(), $1)
                RETURNING id;
                """,
                name,
            )

            # 2. Insert into space_memberships table
            await self._connection.execute(
                """
                INSERT INTO space_memberships (user_id, space_id, role)
                VALUES ($1, $2, 'owner');
                """,
                owner_id,
                space_id,
            )

            return space_id

    async def get_space_by_id(self, space_id: UUID) -> dict | None:
        """Return space row by id or None if not found."""
        row = await self._connection.fetchrow(
            """
            SELECT id, name, deleted_at, delete_scheduled_at
            FROM spaces
            WHERE id = $1;
            """,
            space_id,
        )
        if row is None:
            return None
        return {
            "id": row["id"],
            "name": row["name"],
            "deleted_at": row["deleted_at"],
            "delete_scheduled_at": row["delete_scheduled_at"],
        }

    async def get_membership_role(self, space_id: UUID, user_id: int) -> str | None:
        """Return membership role for the user in the space or None."""
        role = await self._connection.fetchval(
            """
            SELECT role
            FROM space_memberships
            WHERE space_id = $1 AND user_id = $2;
            """,
            space_id,
            user_id,
        )
        return role

    async def mark_deleted(self, space_id: UUID, deleted_at, delete_scheduled_at) -> None:
        """Mark space as deleted (soft delete)."""
        await self._connection.execute(
            """
            UPDATE spaces
            SET deleted_at = $2, delete_scheduled_at = $3
            WHERE id = $1;
            """,
            space_id,
            deleted_at,
            delete_scheduled_at,
        )
