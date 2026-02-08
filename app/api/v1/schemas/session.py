"""Схемы запросов/ответов для эндпойнтов сессий."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.schemas.auth import TokenUserResponse


class SessionCreateResponse(BaseModel):
    """Ответ создания сессии."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "authenticated": True,
                "session_token": "opaque-session-token",
                "expires_at": "2024-01-01T12:00:00Z",
                "user": {
                    "telegram_id": 123456,
                    "username": "user",
                    "created_at": "2024-01-01T12:00:00Z",
                    "last_login_at": "2024-01-01T12:00:00Z",
                },
            }
        }
    )

    authenticated: bool = Field(default=True, description="Session is active")
    session_token: str = Field(..., description="Opaque session token")
    expires_at: datetime
    user: TokenUserResponse


class SessionStatusResponse(BaseModel):
    """Ответ проверки/продления сессии."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "authenticated": True,
                "expires_at": "2024-01-01T12:00:00Z",
                "user": {
                    "telegram_id": 123456,
                    "username": "user",
                    "created_at": "2024-01-01T12:00:00Z",
                    "last_login_at": "2024-01-01T12:00:00Z",
                },
            }
        }
    )

    authenticated: bool = Field(default=True, description="Session is active")
    expires_at: datetime
    user: TokenUserResponse


class SessionLogoutResponse(BaseModel):
    """Ответ для logout (отзыв сессии)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "authenticated": False,
            }
        }
    )

    authenticated: bool = Field(default=False, description="Session is revoked")
