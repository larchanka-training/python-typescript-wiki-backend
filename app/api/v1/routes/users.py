"""API routes for users."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, status

from app.api.deps import get_session_service, get_user_service
from app.api.v1.schemas.users import UserSearchResponse, UserSearchResult
from app.core.errors import AppError, ErrorCode, ErrorResponse
from app.core.trace import get_trace_id
from app.services.session_service import SessionService
from app.services.user_service import UserService

router = APIRouter(tags=["users"])

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


@router.get(
    "/users/search",
    response_model=UserSearchResponse,
    status_code=status.HTTP_200_OK,
    responses=RESPONSES,
    summary="Search users by username",
)
async def search_users(
    request: Request,
    user_service: Annotated[UserService, Depends(get_user_service)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
    q: Annotated[str, Query(min_length=3, max_length=64)],
    limit: Annotated[int, Query(gt=0, le=100)] = 20,
    authorization: Annotated[str | None, Header(description="Bearer session token")] = None,
) -> UserSearchResponse:
    """Searches users by username.

    Requires session authentication via Bearer token.
    Query `q` must be between 3 and 64 characters.
    Possible statuses: 200 OK; 400 VALIDATION_ERROR; 401 SESSION_MISSING/SESSION_EXPIRED;
    500 INTERNAL_ERROR.
    """
    trace_id = get_trace_id(request)
    session_token = _extract_bearer_token(authorization)

    # Check session
    await session_service.get_session(session_token, trace_id)

    users = await user_service.search_users(q, limit)

    return UserSearchResponse(
        users=[UserSearchResult.model_validate(user) for user in users]
    )


def _extract_bearer_token(authorization: str | None) -> str:
    """Extracts bearer token from header."""
    if authorization is None or not authorization.strip():
        raise AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.SESSION_MISSING)
    scheme, _, credentials = authorization.partition(" ")
    if scheme.lower() != "bearer" or not credentials.strip():
        raise AppError(status.HTTP_400_BAD_REQUEST, ErrorCode.VALIDATION_ERROR)
    return credentials.strip()
