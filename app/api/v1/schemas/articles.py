"""Pydantic schemas for articles."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ArticleCreateRequest(BaseModel):
    """Schema for creating a new article."""

    title: str = Field(..., min_length=1, max_length=255, description="Title of the article")
    content: str = Field(..., description="Content of the article in Markdown format")
    show_toc: bool = Field(False, description="Whether to show table of contents")
    parent_id: UUID | None = Field(None, description="Parent article UUID for tree hierarchy")
    position: int = Field(0, description="Sort position within siblings")


class ArticleCreateResponse(BaseModel):
    """Schema for the article creation response."""

    id: UUID = Field(..., description="UUID of the created article")


class ArticleSaveRequest(BaseModel):
    """Payload for saving a new version of an article (PUT)."""

    title: str = Field(..., min_length=1, max_length=255, description="New title")
    content: str = Field(..., description="Updated content in Markdown format")
    show_toc: bool = Field(False, description="Whether to show table of contents")
    content_format: str = Field("markdown", description="Content format (markdown, html, etc.)")
    change_summary: str | None = Field(None, max_length=500, description="Short description of changes")
    base_version_number: int | None = Field(
        None,
        description="Expected current version number for optimistic locking. "
        "If provided and does not match, returns 409.",
    )


class ArticlePermissions(BaseModel):
    """Permissions for performing actions on an article."""

    can_edit: bool = Field(..., description="Whether the user can edit this article")
    can_delete: bool = Field(..., description="Whether the user can delete this article")
    can_lock: bool = Field(..., description="Whether the user can lock/unlock this article")


class ArticleVersionResponse(BaseModel):
    """Schema for returning article version information."""

    id: UUID = Field(..., description="UUID of the version")
    article_id: UUID = Field(..., description="UUID of the article")
    version_number: int = Field(..., description="Version number")
    title: str = Field(..., description="Title of the article at this version")
    content: str = Field(..., description="Content of the article in Markdown format")
    author_id: int | None = Field(None, description="ID of the author (null if user was deleted)")
    author_username: str | None = Field(None, description="Username of the author")
    author_telegram_id: int | None = Field(None, description="Telegram ID of the author")
    show_toc: bool = Field(False, description="Whether to show table of contents")
    content_format: str = Field("markdown", description="Content format")
    change_summary: str | None = Field(None, description="Short description of changes")
    created_at: datetime = Field(..., description="Timestamp when the version was created")
    is_locked: bool = Field(False, description="Whether the article is locked")
    permissions: ArticlePermissions = Field(..., description="Action permissions for the article")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "article_id": "123e4567-e89b-12d3-a456-426614174000",
                "version_number": 1,
                "title": "My Article",
                "content": "# My Article\n\nThis is the content.",
                "author_id": 1,
                "author_username": "jdoe",
                "author_telegram_id": 12345678,
                "show_toc": False,
                "content_format": "markdown",
                "change_summary": None,
                "created_at": "2026-01-01T12:00:00Z",
                "is_locked": False,
                "permissions": {
                    "can_edit": True,
                    "can_delete": False,
                    "can_lock": False,
                },
            }
        }
    }


class ArticleListItem(BaseModel):
    """Single article in a list response."""

    id: UUID = Field(..., description="UUID of the article")
    space_id: UUID = Field(..., description="UUID of the space")
    title: str = Field(..., description="Current article title")
    owner_id: int | None = Field(None, description="ID of the article owner")
    owner_username: str | None = Field(None, description="Username of the article owner")
    owner_telegram_id: int | None = Field(None, description="Telegram ID of the article owner")
    parent_id: UUID | None = Field(None, description="Parent article UUID for tree hierarchy")
    position: int = Field(0, description="Sort position within siblings")
    created_at: datetime = Field(..., description="Timestamp when the article was created")
    updated_at: datetime = Field(..., description="Timestamp of the last update")
    is_locked: bool = Field(False, description="Whether the article is locked")
    permissions: ArticlePermissions | None = Field(None, description="Action permissions for the article")


class ArticleListResponse(BaseModel):
    """Response for listing articles in a space."""

    articles: list[ArticleListItem] = Field(..., description="List of articles")
