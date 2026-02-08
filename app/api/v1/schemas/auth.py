# ruff: noqa: RUF002
"""Схемы запросов/ответов для эндпойнта проверки токена."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TokenRequest(BaseModel):
    """Запрос для проверки access token."""

    token: str = Field(..., min_length=1, description="Encrypted oauth.name access token")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"token": "BASE64_ENCRYPTED_TOKEN"},
        }
    )


class TokenUserResponse(BaseModel):
    """Ответ с пользователем после успешной проверки токена.

    created_at и last_login_at — это timestamps из БД в ISO 8601; created_at из токена не возвращаем.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "telegram_id": 123456,
                "username": "user",
                "created_at": "2024-01-01T12:00:00Z",
                "last_login_at": "2024-01-01T12:00:00Z",
            }
        },
    )

    telegram_id: int
    username: str | None
    created_at: datetime
    last_login_at: datetime


class TokenVerifyResponse(BaseModel):
    """Ответ эндпойнта /token с флагом created и user."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "created": True,
                "user": {
                    "telegram_id": 123456,
                    "username": "user",
                    "created_at": "2024-01-01T12:00:00Z",
                    "last_login_at": "2024-01-01T12:00:00Z",
                },
            }
        }
    )

    created: bool
    user: TokenUserResponse
