"""Service for article-related business logic."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from app.repositories.articles import ArticleRepository, ArticleVersionRepository
    from app.repositories.spaces import SpaceRepository


class ArticleService:
    """Service for article-related operations."""

    def __init__(
        self,
        article_repository: ArticleRepository,
        article_version_repository: ArticleVersionRepository,
        space_repository: SpaceRepository,
    ) -> None:
        self._article_repository = article_repository
        self._article_version_repository = article_version_repository
        self._space_repository = space_repository

    async def create_article(self, space_id: UUID, title: str, content: str, user_id: int) -> UUID:
        """Create a new article in the space.

        Only space owner can create articles.
        """
        # Check if user is owner of the space
        role = await self._space_repository.get_membership_role(space_id, user_id)
        if role != "owner":
            raise PermissionError("Only space owner can create articles")

        # Validate title
        if not title.strip():
            raise ValueError("Title cannot be empty")

        # Create article
        article_id = await self._article_repository.create_article(space_id, title.strip(), user_id)

        # Create first version
        await self._article_version_repository.create_version(
            article_id, 1, title.strip(), content, user_id
        )

        return article_id

    async def get_article_versions(self, article_id: UUID, user_id: int) -> list[dict]:
        """Get all versions of an article.

        User must have access to the space.
        """
        # Get article to check space
        article = await self._article_repository.get_article_by_id(article_id)
        if not article:
            raise ValueError("Article not found")

        # Check access to space
        role = await self._space_repository.get_membership_role(article["space_id"], user_id)
        if role is None:
            raise PermissionError("Access denied")

        # Get versions
        versions = await self._article_version_repository.get_versions_by_article(article_id)
        return versions

    async def get_latest_article_version(self, article_id: UUID, user_id: int) -> dict:
        """Get the latest version of an article.

        User must have access to the space.
        """
        # Get article to check space
        article = await self._article_repository.get_article_by_id(article_id)
        if not article:
            raise ValueError("Article not found")

        # Check access to space
        role = await self._space_repository.get_membership_role(article["space_id"], user_id)
        if role is None:
            raise PermissionError("Access denied")

        # Get latest version
        version = await self._article_version_repository.get_latest_version_by_article(article_id)
        if not version:
            raise ValueError("No versions found for article")

        return version

    async def get_article_version(self, article_id: UUID, version_id: UUID, user_id: int) -> dict:
        """Get a specific version of an article.

        User must have access to the space.
        """
        # First check if article exists and user has access
        article = await self._article_repository.get_article_by_id(article_id)
        if not article:
            raise ValueError("Article not found")

        # Check access to space
        role = await self._space_repository.get_membership_role(article["space_id"], user_id)
        if role is None:
            raise PermissionError("Access denied")

        # Get the version
        version = await self._article_version_repository.get_version_by_id(version_id)
        if not version:
            raise ValueError("Version not found")

        # Verify the version belongs to the requested article
        if version["article_id"] != article_id:
            raise ValueError("Version does not belong to the specified article")

        return version
