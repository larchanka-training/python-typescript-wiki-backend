"""Service for article-related business logic."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from app.repositories.articles import ConflictError  # noqa: TC001

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

    # ── helpers ──────────────────────────────────────────────────────

    async def _require_space_access(self, space_id: UUID, user_id: int) -> str:
        """Return role or raise PermissionError if user has no access."""
        role = await self._space_repository.get_membership_role(space_id, user_id)
        if role is None:
            raise PermissionError("Access denied")
        return role

    async def _require_owner_or_admin(
        self, space_id: UUID, user_id: int, user_permission: str | None,
    ) -> None:
        """Raise PermissionError unless user is space owner or superadmin."""
        if user_permission == "admin":
            return
        role = await self._space_repository.get_membership_role(space_id, user_id)
        if role != "owner":
            raise PermissionError("Only space owner or admin can perform this action")

    def _calculate_permissions(
        self, role: str | None, user_permission: str | None, is_locked: bool,
    ) -> dict:
        """Calculate article action permissions for a user."""
        is_owner_or_admin = (user_permission == "admin") or (role == "owner")
        return {
            "can_edit": is_owner_or_admin and not is_locked,
            "can_delete": is_owner_or_admin,
            "can_lock": is_owner_or_admin,
        }

    async def _get_article_or_404(self, article_id: UUID) -> dict:
        """Return article dict or raise ValueError."""
        article = await self._article_repository.get_article_by_id(article_id)
        if not article:
            raise ValueError("Article not found")
        return article

    # ── public API ──────────────────────────────────────────────────

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
        """Create a new article in the space (transactional).

        Only space owner can create articles.
        """
        role = await self._require_space_access(space_id, user_id)
        if role != "owner":
            raise PermissionError("Only space owner can create articles")

        if not title.strip():
            raise ValueError("Title cannot be empty")

        return await self._article_repository.create_article_with_version(
            space_id,
            title.strip(),
            content,
            user_id,
            show_toc=show_toc,
            parent_id=parent_id,
            position=position,
        )

    async def list_articles(
        self, space_id: UUID, user_id: int, user_permission: str | None, parent_id: UUID | None = None, filter_by_parent: bool = False
    ) -> list[dict]:
        """List all articles in a space (with optional parent_id filtering).

        User must have access to the space.
        """
        role = await self._require_space_access(space_id, user_id)
        articles = await self._article_repository.get_articles_by_space(space_id, parent_id, filter_by_parent)
        for a in articles:
            a["permissions"] = self._calculate_permissions(role, user_permission, a.get("is_locked", False))
        return articles

    async def get_article_path(self, space_id: UUID, article_id: UUID, user_id: int, user_permission: str | None) -> list[dict]:
        """Fetch all ancestors to build a contextual tree."""
        role = await self._require_space_access(space_id, user_id)
        ancestors = await self._article_repository.get_article_ancestors(article_id)
        
        for a in ancestors:
            a["permissions"] = self._calculate_permissions(role, user_permission, a.get("is_locked", False))
        return ancestors

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
        """Save a new version of an existing article (PUT).

        Uses SELECT FOR UPDATE and optional optimistic locking.
        Raises:
            ValueError: article not found or title empty.
            PermissionError: not owner / not admin.
            ConflictError: base_version_number mismatch (→ 409).
        """
        article = await self._get_article_or_404(article_id)

        # Verify article belongs to the expected space
        if article["space_id"] != space_id:
            raise ValueError("Article not found in this space")

        await self._require_owner_or_admin(space_id, user_id, user_permission)

        if article.get("is_locked"):
            raise PermissionError("Article is locked")

        if not title.strip():
            raise ValueError("Title cannot be empty")

        return await self._article_repository.save_new_version(
            article_id,
            title.strip(),
            content,
            user_id,
            show_toc=show_toc,
            content_format=content_format,
            change_summary=change_summary,
            base_version_number=base_version_number,
        )

    async def lock_article(
        self, space_id: UUID, article_id: UUID, user_id: int, user_permission: str | None,
    ) -> None:
        """Lock an article. Only owner or admin allowed."""
        article = await self._get_article_or_404(article_id)
        if article["space_id"] != space_id:
            raise ValueError("Article not found in this space")
        await self._require_owner_or_admin(space_id, user_id, user_permission)
        await self._article_repository.set_locked(article_id, True)

    async def unlock_article(
        self, space_id: UUID, article_id: UUID, user_id: int, user_permission: str | None,
    ) -> None:
        """Unlock an article. Only owner or admin allowed."""
        article = await self._get_article_or_404(article_id)
        if article["space_id"] != space_id:
            raise ValueError("Article not found in this space")
        await self._require_owner_or_admin(space_id, user_id, user_permission)
        await self._article_repository.set_locked(article_id, False)

    async def delete_article(
        self, space_id: UUID, article_id: UUID, user_id: int, user_permission: str | None,
    ) -> None:
        """Soft-delete an article.

        Only the space owner or superadmin may delete.
        """
        article = await self._get_article_or_404(article_id)

        if article["space_id"] != space_id:
            raise ValueError("Article not found in this space")

        await self._require_owner_or_admin(space_id, user_id, user_permission)

        now = datetime.now(timezone.utc)
        await self._article_repository.mark_deleted(article_id, now)

    async def get_article_versions(
        self, space_id: UUID, article_id: UUID, user_id: int, user_permission: str | None,
    ) -> list[dict]:
        """Get all versions of an article.

        User must have access to the space.
        """
        article = await self._get_article_or_404(article_id)
        if article["space_id"] != space_id:
            raise ValueError("Article not found in this space")

        role = await self._require_space_access(space_id, user_id)

        versions = await self._article_version_repository.get_versions_by_article(article_id)
        for v in versions:
            v["is_locked"] = article["is_locked"]
            v["permissions"] = self._calculate_permissions(role, user_permission, article["is_locked"])

        return versions

    async def get_latest_article_version(
        self, space_id: UUID, article_id: UUID, user_id: int, user_permission: str | None,
    ) -> dict:
        """Get the latest version of an article.

        User must have access to the space.
        """
        article = await self._get_article_or_404(article_id)
        if article["space_id"] != space_id:
            raise ValueError("Article not found in this space")

        role = await self._require_space_access(space_id, user_id)

        version = await self._article_version_repository.get_latest_version_by_article(article_id)
        if not version:
            raise ValueError("No versions found for article")

        version["is_locked"] = article["is_locked"]
        version["permissions"] = self._calculate_permissions(role, user_permission, article["is_locked"])

        return version

    async def get_article_version_by_number(
        self, space_id: UUID, article_id: UUID, version_number: int, user_id: int, user_permission: str | None,
    ) -> dict:
        """Get a specific version of an article by its ordinal number.

        User must have access to the space.
        """
        article = await self._get_article_or_404(article_id)
        if article["space_id"] != space_id:
            raise ValueError("Article not found in this space")

        role = await self._require_space_access(space_id, user_id)

        version = await self._article_version_repository.get_version_by_number(
            article_id, version_number
        )
        if not version:
            raise ValueError("Version not found")

        version["is_locked"] = article["is_locked"]
        version["permissions"] = self._calculate_permissions(role, user_permission, article["is_locked"])

        return version
    async def search_articles(self, user_id: int, query: str, limit: int = 20) -> list[dict]:
        """Searches articles by title and content."""
        return await self._article_repository.search_articles(user_id, query, limit)

    async def get_recent_articles(self, user_id: int, limit: int = 10) -> list[dict]:
        """Get latest user-touched articles."""
        return await self._article_repository.get_recent_articles_by_user(user_id, limit)
