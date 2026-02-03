# ruff: noqa: RUF002
"""Бизнес-логика аутентификации."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import status

from app.core.errors import AppError, ErrorCode

if TYPE_CHECKING:
    from app.repositories.users import UserRepository
    from app.services.models import UserProfile
    from app.services.token_service import TokenService

logger = logging.getLogger(__name__)


class AuthService:
    """Проверяет токен и делает upsert пользователя по telegram_id."""

    def __init__(self, token_service: TokenService, user_repository: UserRepository) -> None:
        self._token_service = token_service
        self._user_repository = user_repository

    async def verify_token(self, token: str, trace_id: str) -> tuple[UserProfile, bool]:
        """Локально валидирует токен, затем upsert пользователя.

        Возвращает (user, created), где created=True при создании новой записи.
        Любая ошибка валидации/БД -> AppError с контрактным кодом.
        """
        payload = self._token_service.verify_token(token, trace_id=trace_id)

        try:
            user, created = await self._user_repository.upsert_user(
                telegram_id=payload.telegram_id,
                username=payload.username,
                first_name=payload.first_name,
                last_name=payload.last_name,
                photo_url=payload.photo_url,
                permission=payload.permission,
            )
            promoted = await self._user_repository.ensure_first_superuser(user.id)
        except Exception as exc:
            logger.exception(
                "user upsert failed: telegram_id=%s trace_id=%s",
                payload.telegram_id,
                trace_id,
            )
            raise AppError(status.HTTP_500_INTERNAL_SERVER_ERROR, ErrorCode.INTERNAL_ERROR) from exc

        if promoted:
            user.is_superuser = True

        logger.info(
            "user upserted: telegram_id=%s created=%s trace_id=%s",
            payload.telegram_id,
            created,
            trace_id,
        )
        return user, created
