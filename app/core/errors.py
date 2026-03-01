# ruff: noqa: RUF002
"""Типы ошибок и обработчики."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import logging
from typing import TYPE_CHECKING, Literal

from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.trace import get_trace_id

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from fastapi import Request
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException


class ErrorCode(str, Enum):
    """Коды ошибок, которые фронт использует для локализации."""

    VALIDATION_ERROR = "VALIDATION_ERROR"  # Невалидный запрос (400).
    OAUTH_CODE_INVALID = "OAUTH_CODE_INVALID"  # Токен невалиден/просрочен (401).
    OAUTH_STATE_INVALID = "OAUTH_STATE_INVALID"  # Некорректный state (401).
    SESSION_MISSING = "SESSION_MISSING"  # Сессия не передана (401).
    SESSION_EXPIRED = "SESSION_EXPIRED"  # Сессия истекла/отозвана (401).
    NOT_FOUND = "NOT_FOUND"  # Ресурс не найден (404).
    FORBIDDEN = "FORBIDDEN"  # Нет доступа (403).
    ARTICLE_VERSION_CONFLICT = "ARTICLE_VERSION_CONFLICT"  # Конфликт версий (409).
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"  # Лимит запросов (429).
    INTERNAL_ERROR = "INTERNAL_ERROR"  # Внутренняя ошибка (500).


class ErrorResponse(BaseModel):
    """Единый формат ошибок API: {status,message,timestamp}."""

    status: Literal["error"] = Field("error", description="Fixed error marker")
    message: ErrorCode = Field(..., description="Machine-readable error code")
    timestamp: str = Field(..., description="UTC timestamp in ISO 8601 format")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "error",
                "message": "INTERNAL_ERROR",
                "timestamp": "2025-01-01T12:00:00Z",
            }
        }
    }


class AppError(Exception):
    """Доменная ошибка с HTTP статусом и ErrorCode для единообразного ответа."""

    def __init__(self, status_code: int, code: ErrorCode) -> None:
        super().__init__(code.value)
        self.status_code = status_code
        self.code = code


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Преобразует AppError в стандартный ответ {status,message,timestamp}."""
    _ = request
    # Доменные ошибки (например, OAUTH_CODE_INVALID/INTERNAL_ERROR) проходят через AppError.
    payload = _error_payload(exc.code)
    return JSONResponse(status_code=exc.status_code, content=payload)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Возвращает VALIDATION_ERROR для ошибок Pydantic (вместо 422)."""
    trace_id = get_trace_id(request)
    logger.warning("request validation error: %s trace_id=%s", exc.errors(), trace_id)
    # Валидация запроса всегда 400 VALIDATION_ERROR (не 422).
    payload = _error_payload(ErrorCode.VALIDATION_ERROR)
    return JSONResponse(status_code=400, content=payload)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Маппит HTTPException в ErrorCode, сохраняя контрактные статусы."""
    _ = request
    code = {
        400: ErrorCode.VALIDATION_ERROR,
        401: ErrorCode.OAUTH_CODE_INVALID,
        403: ErrorCode.FORBIDDEN,
        404: ErrorCode.NOT_FOUND,
        409: ErrorCode.ARTICLE_VERSION_CONFLICT,
        422: ErrorCode.VALIDATION_ERROR,
        429: ErrorCode.RATE_LIMIT_EXCEEDED,
    }.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
    payload = _error_payload(code)
    return JSONResponse(status_code=exc.status_code, content=payload)


async def rate_limit_exception_handler(request: Request, _exc: Exception) -> JSONResponse:
    """Возвращает единый формат ошибки для rate limit."""
    _ = request
    payload = _error_payload(ErrorCode.RATE_LIMIT_EXCEEDED)
    return JSONResponse(status_code=429, content=payload)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all для неожиданных ошибок (500 INTERNAL_ERROR)."""
    trace_id = get_trace_id(request)
    logger.exception("unhandled error: %s trace_id=%s", exc, trace_id)
    payload = _error_payload(ErrorCode.INTERNAL_ERROR)
    return JSONResponse(status_code=500, content=payload)


def _error_payload(code: ErrorCode) -> dict[str, str]:
    timestamp = _utc_timestamp()
    response = ErrorResponse(message=code, timestamp=timestamp)
    return response.model_dump()


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
