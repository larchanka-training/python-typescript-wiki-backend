# ruff: noqa: RUF002
"""Эндпойнты для работы с сессиями."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, Request, status

from app.api.deps import get_session_service
from app.api.v1.schemas.auth import TokenRequest, TokenUserResponse
from app.api.v1.schemas.session import SessionCreateResponse, SessionLogoutResponse, SessionStatusResponse
from app.core.errors import AppError, ErrorCode, ErrorResponse
from app.core.trace import get_trace_id
from app.services.session_service import SessionService  # noqa: TC001

router = APIRouter(tags=["auth"])

RESPONSES = {
    status.HTTP_400_BAD_REQUEST: {
        "model": ErrorResponse,
        "description": "Validation error",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Validation error",
                        "value": {
                            "status": "error",
                            "message": "VALIDATION_ERROR",
                            "timestamp": "2025-01-01T12:00:00Z",
                        },
                    }
                }
            }
        },
    },
    status.HTTP_401_UNAUTHORIZED: {
        "model": ErrorResponse,
        "description": "Unauthorized",
        "content": {
            "application/json": {
                "examples": {
                    "session_missing": {
                        "summary": "Session missing",
                        "value": {
                            "status": "error",
                            "message": "SESSION_MISSING",
                            "timestamp": "2025-01-01T12:00:00Z",
                        },
                    },
                    "session_expired": {
                        "summary": "Session expired/revoked",
                        "value": {
                            "status": "error",
                            "message": "SESSION_EXPIRED",
                            "timestamp": "2025-01-01T12:00:00Z",
                        },
                    },
                    "oauth_invalid": {
                        "summary": "OAuth token invalid",
                        "value": {
                            "status": "error",
                            "message": "OAUTH_CODE_INVALID",
                            "timestamp": "2025-01-01T12:00:00Z",
                        },
                    },
                }
            }
        },
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "model": ErrorResponse,
        "description": "Internal server error",
        "content": {
            "application/json": {
                "examples": {
                    "internal_error": {
                        "summary": "Internal error",
                        "value": {
                            "status": "error",
                            "message": "INTERNAL_ERROR",
                            "timestamp": "2025-01-01T12:00:00Z",
                        },
                    }
                }
            }
        },
    },
}


@router.post(
    "/session",
    response_model=SessionCreateResponse,
    status_code=status.HTTP_200_OK,
    responses=RESPONSES,
    summary="Create a session after token verification",
)
async def create_session(
    request: Request,
    session_service: Annotated[SessionService, Depends(get_session_service)],
    body: Annotated[TokenRequest, Body()],
) -> SessionCreateResponse:
    """Создаёт сессию после проверки oauth.name токена.

    Возможные статусы: 200 OK; 400 VALIDATION_ERROR; 401 OAUTH_CODE_INVALID;
    500 INTERNAL_ERROR. Ошибки всегда возвращаются в формате {status,message,timestamp}.
    """
    trace_id = get_trace_id(request)
    token = body.token.strip()
    if not token:
        # Контракт требует 400 VALIDATION_ERROR вместо 422.
        raise AppError(status.HTTP_400_BAD_REQUEST, ErrorCode.VALIDATION_ERROR)

    data = await session_service.create_session(token, trace_id)
    if data.session_token is None:
        raise AppError(status.HTTP_500_INTERNAL_SERVER_ERROR, ErrorCode.INTERNAL_ERROR)
    return SessionCreateResponse(
        authenticated=True,
        session_token=data.session_token,
        expires_at=data.expires_at,
        user=TokenUserResponse.model_validate(data.user),
    )


@router.get(
    "/session",
    response_model=SessionStatusResponse,
    status_code=status.HTTP_200_OK,
    responses=RESPONSES,
    summary="Check current session",
)
async def get_session(
    request: Request,
    session_service: Annotated[SessionService, Depends(get_session_service)],
    authorization: Annotated[str | None, Header(description="Bearer session token")] = None,
) -> SessionStatusResponse:
    """Проверяет текущую сессию по Authorization: Bearer <token>.

    Возможные статусы: 200 OK; 401 SESSION_MISSING/SESSION_EXPIRED; 400 VALIDATION_ERROR
    при неверном формате заголовка.
    """
    trace_id = get_trace_id(request)
    session_token = _extract_bearer_token(authorization)
    data = await session_service.get_session(session_token, trace_id)
    return SessionStatusResponse(
        authenticated=True,
        expires_at=data.expires_at,
        user=TokenUserResponse.model_validate(data.user),
    )


@router.post(
    "/session/refresh",
    response_model=SessionStatusResponse,
    status_code=status.HTTP_200_OK,
    responses=RESPONSES,
    summary="Refresh session expiration",
)
async def refresh_session(
    request: Request,
    session_service: Annotated[SessionService, Depends(get_session_service)],
    authorization: Annotated[str | None, Header(description="Bearer session token")] = None,
) -> SessionStatusResponse:
    """Продлевает срок жизни сессии по Authorization: Bearer <token>.

    Возможные статусы: 200 OK; 401 SESSION_MISSING/SESSION_EXPIRED; 400 VALIDATION_ERROR
    при неверном формате заголовка.
    """
    trace_id = get_trace_id(request)
    session_token = _extract_bearer_token(authorization)
    data = await session_service.refresh_session(session_token, trace_id)
    return SessionStatusResponse(
        authenticated=True,
        expires_at=data.expires_at,
        user=TokenUserResponse.model_validate(data.user),
    )


@router.delete(
    "/session",
    response_model=SessionLogoutResponse,
    status_code=status.HTTP_200_OK,
    responses=RESPONSES,
    summary="Revoke current session",
)
async def delete_session(
    request: Request,
    session_service: Annotated[SessionService, Depends(get_session_service)],
    authorization: Annotated[str | None, Header(description="Bearer session token")] = None,
) -> SessionLogoutResponse:
    """Отзывает сессию по Authorization: Bearer <token>.

    Возможные статусы: 200 OK; 401 SESSION_MISSING/SESSION_EXPIRED; 400 VALIDATION_ERROR
    при неверном формате заголовка.
    """
    trace_id = get_trace_id(request)
    session_token = _extract_bearer_token(authorization)
    await session_service.revoke_session(session_token, trace_id)
    return SessionLogoutResponse(authenticated=False)


def _extract_bearer_token(authorization: str | None) -> str:
    """Извлекает bearer-токен или возвращает ошибку по контракту."""
    if authorization is None or not authorization.strip():
        raise AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.SESSION_MISSING)
    scheme, _, credentials = authorization.partition(" ")
    if scheme.lower() != "bearer" or not credentials.strip():
        # Неверный формат заголовка — это 400 VALIDATION_ERROR, не 401.
        raise AppError(status.HTTP_400_BAD_REQUEST, ErrorCode.VALIDATION_ERROR)
    return credentials.strip()
