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


@router.get(
    "/spaces/{space_id}",
    response_model=SpaceResponse,
    status_code=status.HTTP_200_OK,
    responses=RESPONSES | {
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Access forbidden (soft-deleted space >7 days for non-admin)",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Space not found or not accessible",
        },
    },
    summary="Get space by ID",
    description="Retrieve space details with soft-delete visibility rules. Soft-deleted spaces are only visible to owner (within 7 days) and superadmin.",
)
async def get_space_by_id(
    request: Request,
    space_id: str = Annotated[str, ...],
    space_service: Annotated[SpaceService, Depends(get_space_service)] = None,
    session_service: Annotated[SessionService, Depends(get_session_service)] = None,
    authorization: Annotated[str | None, Header(description="Bearer session token")] = None,
) -> SpaceResponse:
    """Get a space by its ID.

    **Soft-delete visibility:**
    - Active spaces: visible to all authenticated users
    - Deleted spaces (≤7 days): visible to owner and superadmin with `deleted=true`
    - Deleted spaces (>7 days): visible only to superadmin

    **Response fields:**
    - `id`: UUID of the space
    - `name`: Name of the space
    - `deleted`: Boolean flag (true if soft-deleted)
    - `deleted_at`: Timestamp when deleted (null if active)
    - `delete_scheduled_at`: Timestamp when hard-delete is scheduled (null if active)

    **Status codes:**
    - 200: Space retrieved successfully
    - 401: Missing or invalid session token
    - 403: Access forbidden (space deleted >7 days for non-admin)
    - 404: Space not found
    - 500: Internal server error
    """
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

    return SpaceResponse(**space)


@router.delete(
    "/spaces/{space_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=RESPONSES | {
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Insufficient permissions (only owner or superadmin can delete)",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Space not found",
        },
    },
    summary="Soft-delete a space",
    description="Mark a space as deleted. Sets a 7-day recovery window. Data is never physically deleted from the database.",
)
async def delete_space(
    request: Request,
    space_id: str = Annotated[str, ...],
    space_service: Annotated[SpaceService, Depends(get_space_service)] = None,
    session_service: Annotated[SessionService, Depends(get_session_service)] = None,
    authorization: Annotated[str | None, Header(description="Bearer session token")] = None,
) -> None:
    """Soft-delete a space (never physically removed from database).

    **Permissions:**
    - Only the owner of the space or superadmin can delete

    **Behavior:**
    - Sets `deleted_at` to current timestamp
    - Sets `delete_scheduled_at` to current timestamp + 7 days
    - Owner can restore the space using PATCH /spaces/{space_id}/restore within 7 days
    - After 7 days, only superadmin can restore it

    **Status codes:**
    - 204: Space successfully marked as deleted (no response body)
    - 401: Missing or invalid session token
    - 403: Insufficient permissions (only owner or superadmin can delete)
    - 404: Space not found
    - 500: Internal server error
    """
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


@router.patch(
    "/spaces/{space_id}/restore",
    response_model=SpaceResponse,
    status_code=status.HTTP_200_OK,
    responses=RESPONSES | {
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Recovery window expired (owner) or insufficient permissions",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Space not found or not deleted",
        },
    },
    summary="Restore a soft-deleted space",
    description="Restore a soft-deleted space. Owner can restore within 7 days; superadmin can restore anytime.",
)
async def restore_space(
    request: Request,
    space_id: str = Annotated[str, ...],
    space_service: Annotated[SpaceService, Depends(get_space_service)] = None,
    session_service: Annotated[SessionService, Depends(get_session_service)] = None,
    authorization: Annotated[str | None, Header(description="Bearer session token")] = None,
) -> SpaceResponse:
    """Restore a soft-deleted space to active status.

    **Permissions:**
    - Superadmin: can restore any soft-deleted space at any time
    - Owner: can restore only within 7 days of deletion (before `delete_scheduled_at`)

    **Behavior:**
    - Clears `deleted_at` (sets to NULL)
    - Clears `delete_scheduled_at` (sets to NULL)
    - Space becomes `deleted: false` and visible to all authenticated users

    **Response:**
    - Returns the restored space with `deleted: false` and all fields populated

    **Status codes:**
    - 200: Space successfully restored, returns space details
    - 401: Missing or invalid session token
    - 403: Recovery window expired (owner) or insufficient permissions
    - 404: Space not found or not deleted
    - 500: Internal server error
    """
    trace_id = get_trace_id(request)
    session_token = _extract_bearer_token(authorization)
    session_data = await session_service.get_session(session_token, trace_id)
    try:
        space_uuid = UUID(space_id)
        await space_service.restore_space(space_uuid, session_data.user)
        space = await space_service.get_space(space_uuid, session_data.user)
    except ValueError:
        raise AppError(status.HTTP_404_NOT_FOUND, ErrorCode.VALIDATION_ERROR)
    except PermissionError:
        raise AppError(status.HTTP_403_FORBIDDEN, ErrorCode.VALIDATION_ERROR)

    return SpaceResponse(**space)
