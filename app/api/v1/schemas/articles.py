"""Pydantic schemas for articles."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ArticleCreateRequest(BaseModel):
    """Schema for creating a new article."""

    title: str = Field(..., min_length=1, max_length=255, description="Title of the article")
    content: str = Field(..., description="Content of the article in Markdown format")


class ArticleCreateResponse(BaseModel):
    """Schema for the article creation response."""

    id: UUID = Field(..., description="UUID of the created article")


class ArticleUpdateRequest(BaseModel):
    """Payload when updating an existing article."""

    title: str = Field(..., min_length=1, max_length=255, description="New title")
    content: str = Field(..., description="Updated content in Markdown format")

    model_config = {"json_schema_extra": {"example": {"id": "123e4567-e89b-12d3-a456-426614174000"}}}


class ArticleVersionResponse(BaseModel):
    """Schema for returning article version information."""

    id: UUID = Field(..., description="UUID of the version")
    article_id: UUID = Field(..., description="UUID of the article")
    version_number: int = Field(..., description="Version number")
    title: str = Field(..., description="Title of the article at this version")
    content: str = Field(..., description="Content of the article in Markdown format")
    author_id: int = Field(..., description="ID of the author")
    created_at: datetime = Field(..., description="Timestamp when the version was created")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "article_id": "123e4567-e89b-12d3-a456-426614174000",
                "version_number": 1,
                "title": "My Article",
                "content": "# My Article\n\nThis is the content.",
                "author_id": 1,
                "created_at": "2026-01-01T12:00:00Z",
            }
        }
    }
