"""API routes for spaces."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, Request, status

from app.api.deps import get_session_service, get_space_service
from app.api.v1.schemas.spaces import SpaceCreateRequest, SpaceCreateResponse
from app.api.v1.schemas.spaces import SpaceResponse
from uuid import UUID
from app.core.errors import AppError, ErrorCode, ErrorResponse
from app.core.trace import get_trace_id
from app.services.session_service import SessionService
from app.services.space_service import SpaceService

router = APIRouter(tags=["spaces"])

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


@router.post(
    "/spaces",
    response_model=SpaceCreateResponse,
    status_code=status.HTTP_201_CREATED,
    responses=RESPONSES,
    summary="Create a new space",
)
async def create_space(
    request: Request,
    space_service: Annotated[SpaceService, Depends(get_space_service)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
    body: Annotated[SpaceCreateRequest, Body()],
    authorization: Annotated[str | None, Header(description="Bearer session token")] = None,
) -> SpaceCreateResponse:
    """Creates a new space.

    Requires session authentication via Bearer token.
    Possible statuses: 201 Created; 400 VALIDATION_ERROR; 401 SESSION_MISSING/SESSION_EXPIRED;
    500 INTERNAL_ERROR.
    """
    trace_id = get_trace_id(request)
    session_token = _extract_bearer_token(authorization)

    # Check session and get user_id
    session_data = await session_service.get_session(session_token, trace_id)
    user_id = session_data.user.id

    if not body.name.strip():
        raise AppError(status.HTTP_400_BAD_REQUEST, ErrorCode.VALIDATION_ERROR)

    space_id = await space_service.create_space(body.name, user_id)
    return SpaceCreateResponse(id=space_id)


def _extract_bearer_token(authorization: str | None) -> str:
    """Extracts bearer token from header."""
    if authorization is None or not authorization.strip():
        raise AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.SESSION_MISSING)
    scheme, _, credentials = authorization.partition(" ")
    if scheme.lower() != "bearer" or not credentials.strip():
        raise AppError(status.HTTP_400_BAD_REQUEST, ErrorCode.VALIDATION_ERROR)
    return credentials.strip()


@router.get("/spaces/{space_id}", response_model=SpaceResponse, summary="Get space by id")
async def get_space_by_id(
    request: Request,
    space_id: str,
    space_service: Annotated[SpaceService, Depends(get_space_service)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
    authorization: Annotated[str | None, Header(description="Bearer session token")] = None,
) -> SpaceResponse:
    trace_id = get_trace_id(request)
    session_token = _extract_bearer_token(authorization)
    session_data = await session_service.get_session(session_token, trace_id)
    try:
        space_uuid = UUID(space_id)
        space = await space_service.get_space(space_uuid, session_data.user)
    except ValueError:
        raise AppError(status.HTTP_404_NOT_FOUND, ErrorCode.VALIDATION_ERROR)
    except PermissionError:
        raise AppError(status.HTTP_403_FORBIDDEN, ErrorCode.VALIDATION_ERROR)

    # Normalize response to include optional datetime fields if present
    return SpaceResponse(**space)


@router.delete("/spaces/{space_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Soft-delete a space")
async def delete_space(
    request: Request,
    space_id: str,
    space_service: Annotated[SpaceService, Depends(get_space_service)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
    authorization: Annotated[str | None, Header(description="Bearer session token")] = None,
) -> None:
    trace_id = get_trace_id(request)
    session_token = _extract_bearer_token(authorization)
    session_data = await session_service.get_session(session_token, trace_id)
    try:
        space_uuid = UUID(space_id)
        await space_service.delete_space(space_uuid, session_data.user)
    except ValueError:
        raise AppError(status.HTTP_404_NOT_FOUND, ErrorCode.VALIDATION_ERROR)
    except PermissionError:
        raise AppError(status.HTTP_403_FORBIDDEN, ErrorCode.VALIDATION_ERROR)
