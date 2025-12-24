"""Эндпойнты аутентификации для проверки токена и upsert пользователя."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request, status

from app.api.deps import get_auth_service
from app.api.v1.schemas.auth import TokenRequest, TokenUserResponse, TokenVerifyResponse
from app.core.errors import AppError, ErrorCode, ErrorResponse
from app.core.trace import get_trace_id
from app.services.auth_service import AuthService  # noqa: TC001

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
                    "token_invalid": {
                        "summary": "Token invalid/expired",
                        "value": {
                            "status": "error",
                            "message": "OAUTH_CODE_INVALID",
                            "timestamp": "2025-01-01T12:00:00Z",
                        },
                    }
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
    "/token",
    response_model=TokenVerifyResponse,
    status_code=status.HTTP_200_OK,
    responses=RESPONSES,
    summary="Verify access token and upsert user",
)
async def verify_token(
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    body: Annotated[TokenRequest, Body()],
) -> TokenVerifyResponse:
    """Проверяет токен oauth.name, делает upsert пользователя и возвращает {created, user}.

    Статусы: 200 OK; 400 VALIDATION_ERROR (включая валидацию запроса, без 422);
    401 OAUTH_CODE_INVALID; 500 INTERNAL_ERROR. created_at из токена используется
    только для TTL и в ответ не попадает (возвращается created_at из БД).
    """
    trace_id = get_trace_id(request)
    # Не логируем raw token; достаточно trace_id и кода ошибки.  # noqa: RUF003
    token = body.token.strip()
    if not token:
        # Контракт требует 400 VALIDATION_ERROR вместо 422.
        raise AppError(status.HTTP_400_BAD_REQUEST, ErrorCode.VALIDATION_ERROR)

    user, created = await auth_service.verify_token(token, trace_id)
    return TokenVerifyResponse(
        created=created,
        user=TokenUserResponse.model_validate(user),
    )
