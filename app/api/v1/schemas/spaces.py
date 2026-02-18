"""Pydantic schemas for spaces."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SpaceCreateRequest(BaseModel):
    """Schema for creating a new space."""

    name: str = Field(..., min_length=1, max_length=255, description="Name of the space")


class SpaceCreateResponse(BaseModel):
    """Schema for the space creation response."""

    id: UUID = Field(..., description="UUID of the created space")

    model_config = {"json_schema_extra": {"example": {"id": "123e4567-e89b-12d3-a456-426614174000"}}}


class SpaceResponse(BaseModel):
    """Schema for returning space information."""
    id: UUID = Field(..., description="UUID of the space")
    name: str = Field(..., description="Name of the space")
    deleted: bool = Field(False, description="Soft-deleted marker")
    deleted_at: datetime | None = Field(None, description="When deletion was requested")
    delete_scheduled_at: datetime | None = Field(None, description="When the space becomes hidden for non-admins")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "My Space",
                "deleted": True,
                "deleted_at": "2026-01-01T12:00:00Z",
                "delete_scheduled_at": "2026-01-08T12:00:00Z",
            }
        }
    }
