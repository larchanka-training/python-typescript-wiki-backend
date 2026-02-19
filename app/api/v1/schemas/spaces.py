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
    """Schema for returning space information with soft-delete status.
    
    **Soft-delete fields:**
    - `deleted`: True if space is soft-deleted; false if active
    - `deleted_at`: Timestamp when deletion was requested (UTC); null if active
    - `delete_scheduled_at`: Timestamp when space becomes hidden from non-admins (UTC); null if active
    
    **Visibility rules:**
    - Active spaces: visible to all authenticated users
    - Deleted ≤7 days: visible to owner+admin with deleted timestamps shown
    - Deleted >7 days: visible to admin only with deleted timestamps shown
    """
    id: UUID = Field(..., description="UUID of the space (primary identifier)")
    name: str = Field(..., description="Name of the space (max 255 characters)")
    deleted: bool = Field(False, description="True if space is soft-deleted; false if active")
    deleted_at: datetime | None = Field(None, description="Timestamp when deletion was initiated (ISO 8601 UTC); null for active spaces")
    delete_scheduled_at: datetime | None = Field(None, description="Timestamp when space becomes hidden from non-admins (ISO 8601 UTC, typically 7 days after deleted_at); null for active spaces")

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


class SpaceListItem(BaseModel):
    """Schema for a space in the list."""

    id: UUID = Field(..., description="UUID of the space")
    name: str = Field(..., description="Name of the space")
    role: str = Field(..., description="User's role in the space")
    is_deleted: bool = Field(..., description="Whether the space is deleted")
    deleted_at: datetime | None = Field(None, description="Timestamp when the space was deleted")


class SpaceListResponse(BaseModel):
    """Schema for the spaces list response."""

    spaces: list[SpaceListItem] = Field(..., description="List of spaces")

    model_config = {
        "json_schema_extra": {
            "example": {
                "spaces": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "name": "My Space",
                        "role": "owner",
                        "is_deleted": False,
                        "deleted_at": None,
                    }
                ]
            }
        }
    }
