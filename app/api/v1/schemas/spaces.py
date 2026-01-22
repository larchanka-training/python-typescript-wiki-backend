"""Pydantic schemas for spaces."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class SpaceCreateRequest(BaseModel):
    """Schema for creating a new space."""

    name: str = Field(..., min_length=1, max_length=255, description="Name of the space")


class SpaceCreateResponse(BaseModel):
    """Schema for the space creation response."""

    id: UUID = Field(..., description="UUID of the created space")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }
    }
