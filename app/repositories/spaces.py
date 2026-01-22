"""Repositories for spaces."""

from __future__ import annotations

from typing import TYPE_CHECKING

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
