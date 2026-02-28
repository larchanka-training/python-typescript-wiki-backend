"""API routes for articles."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, Request, status

from app.api.deps import get_article_service, get_session_service
from app.api.v1.schemas.articles import (
    ArticleCreateRequest,
    ArticleCreateResponse,
    ArticleUpdateRequest,
    ArticleVersionResponse,
)
from app.core.errors import AppError, ErrorCode, ErrorResponse
from app.core.trace import get_trace_id
from app.services.article_service import ArticleService  # noqa: TC001
from app.services.session_service import SessionService  # noqa: TC001

router = APIRouter(tags=["articles"])

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
    status.HTTP_403_FORBIDDEN: {
        "model": ErrorResponse,
        "description": "Forbidden",
        "content": {
            "application/json": {
                "examples": {
                    "forbidden": {
                        "summary": "Forbidden",
                        "value": {
                            "status": "error",
                            "message": "FORBIDDEN",
                            "timestamp": "2025-01-01T12:00:00Z",
                        },
                    }
                }
            }
        },
    },
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorResponse,
        "description": "Not found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Not found",
                        "value": {
                            "status": "error",
                            "message": "NOT_FOUND",
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
    "/spaces/{space_id}/articles",
    response_model=ArticleCreateResponse,
    status_code=status.HTTP_201_CREATED,
    responses=RESPONSES,
    summary="Create a new article",
)
async def create_article(  # noqa: PLR0913
    request: Request,
    space_id: UUID,
    article_service: Annotated[ArticleService, Depends(get_article_service)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
    body: Annotated[ArticleCreateRequest, Body()],
    authorization: Annotated[str | None, Header(description="Bearer session token")] = None,
) -> ArticleCreateResponse:
    """Creates a new article in the specified space.

    Only the space owner can create articles.
    Requires session authentication via Bearer token.
    Possible statuses: 201 Created; 400 VALIDATION_ERROR; 401 SESSION_MISSING/SESSION_EXPIRED;
    403 FORBIDDEN; 404 NOT_FOUND; 500 INTERNAL_ERROR.
    """
    trace_id = get_trace_id(request)
    session_token = _extract_bearer_token(authorization)

    # Check session and get user_id
    session_data = await session_service.get_session(session_token, trace_id)
    user_id = session_data.user.id

    try:
        article_id = await article_service.create_article(space_id, body.title, body.content, user_id)
        return ArticleCreateResponse(id=article_id)
    except ValueError as e:
        if "not found" in str(e):
            raise AppError(status.HTTP_404_NOT_FOUND, ErrorCode.NOT_FOUND) from None
        raise AppError(status.HTTP_400_BAD_REQUEST, ErrorCode.VALIDATION_ERROR) from None
    except PermissionError:
        raise AppError(status.HTTP_403_FORBIDDEN, ErrorCode.FORBIDDEN) from None


@router.patch(
    "/articles/{article_id}",
    response_model=ArticleVersionResponse,
    status_code=status.HTTP_200_OK,
    responses=RESPONSES,
    summary="Update an existing article",
)
async def update_article(
    request: Request,
    article_id: UUID,
    article_service: Annotated[ArticleService, Depends(get_article_service)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
    body: Annotated[ArticleUpdateRequest, Body()],
    authorization: Annotated[str | None, Header(description="Bearer session token")] = None,
) -> ArticleVersionResponse:
    """Updates an existing article and creates a new version.

    Only the space owner or superadmin may update an article.
    """
    trace_id = get_trace_id(request)
    session_token = _extract_bearer_token(authorization)

    # validate session
    session_data = await session_service.get_session(session_token, trace_id)
    user_id = session_data.user.id
    user_perm = session_data.user.permission

    try:
        version_id = await article_service.update_article(
            article_id, body.title, body.content, user_id, user_perm
        )
        version = await article_service.get_article_version(article_id, version_id, user_id)
        return ArticleVersionResponse(**version)
    except ValueError as e:
        if "not found" in str(e):
            raise AppError(status.HTTP_404_NOT_FOUND, ErrorCode.NOT_FOUND) from None
        raise AppError(status.HTTP_400_BAD_REQUEST, ErrorCode.VALIDATION_ERROR) from None
    except PermissionError:
        raise AppError(status.HTTP_403_FORBIDDEN, ErrorCode.FORBIDDEN) from None


@router.get(
    "/articles/{article_id}/versions",
    response_model=list[ArticleVersionResponse],
    status_code=status.HTTP_200_OK,
    responses=RESPONSES,
    summary="Get all versions of an article",
)
async def get_article_versions(
    request: Request,
    article_id: UUID,
    article_service: Annotated[ArticleService, Depends(get_article_service)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
    authorization: Annotated[str | None, Header(description="Bearer session token")] = None,
) -> list[ArticleVersionResponse]:
    """Gets all versions of the specified article.

    User must have access to the space containing the article.
    Requires session authentication via Bearer token.
    Possible statuses: 200 OK; 401 SESSION_MISSING/SESSION_EXPIRED;
    403 FORBIDDEN; 404 NOT_FOUND; 500 INTERNAL_ERROR.
    """
    trace_id = get_trace_id(request)
    session_token = _extract_bearer_token(authorization)

    # Check session and get user_id
    session_data = await session_service.get_session(session_token, trace_id)
    user_id = session_data.user.id

    try:
        versions = await article_service.get_article_versions(article_id, user_id)
        return [ArticleVersionResponse(**version) for version in versions]
    except ValueError as e:
        if "not found" in str(e):
            raise AppError(status.HTTP_404_NOT_FOUND, ErrorCode.NOT_FOUND) from None
        raise AppError(status.HTTP_400_BAD_REQUEST, ErrorCode.VALIDATION_ERROR) from None
    except PermissionError:
        raise AppError(status.HTTP_403_FORBIDDEN, ErrorCode.FORBIDDEN) from None


@router.get(
    "/articles/{article_id}",
    response_model=ArticleVersionResponse,
    status_code=status.HTTP_200_OK,
    responses=RESPONSES,
    summary="Get the latest version of an article",
)
async def get_article(
    request: Request,
    article_id: UUID,
    article_service: Annotated[ArticleService, Depends(get_article_service)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
    authorization: Annotated[str | None, Header(description="Bearer session token")] = None,
) -> ArticleVersionResponse:
    """Gets the latest version of the specified article.

    User must have access to the space containing the article.
    Requires session authentication via Bearer token.
    Possible statuses: 200 OK; 401 SESSION_MISSING/SESSION_EXPIRED;
    403 FORBIDDEN; 404 NOT_FOUND; 500 INTERNAL_ERROR.
    """
    trace_id = get_trace_id(request)
    session_token = _extract_bearer_token(authorization)

    # Check session and get user_id
    session_data = await session_service.get_session(session_token, trace_id)
    user_id = session_data.user.id

    try:
        version = await article_service.get_latest_article_version(article_id, user_id)
        return ArticleVersionResponse(**version)
    except ValueError as e:
        if "not found" in str(e):
            raise AppError(status.HTTP_404_NOT_FOUND, ErrorCode.NOT_FOUND) from None
        raise AppError(status.HTTP_400_BAD_REQUEST, ErrorCode.VALIDATION_ERROR) from None
    except PermissionError:
        raise AppError(status.HTTP_403_FORBIDDEN, ErrorCode.FORBIDDEN) from None


@router.get(
    "/articles/{article_id}/{version_id}",
    response_model=ArticleVersionResponse,
    status_code=status.HTTP_200_OK,
    responses=RESPONSES,
    summary="Get a specific version of an article",
)
async def get_article_version(
    request: Request,
    article_id: UUID,
    version_id: UUID,
    article_service: Annotated[ArticleService, Depends(get_article_service)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
    authorization: Annotated[str | None, Header(description="Bearer session token")] = None,
) -> ArticleVersionResponse:
    """Gets the specified version of an article.

    User must have access to the space containing the article.
    Requires session authentication via Bearer token.
    Possible statuses: 200 OK; 401 SESSION_MISSING/SESSION_EXPIRED;
    403 FORBIDDEN; 404 NOT_FOUND; 500 INTERNAL_ERROR.
    """
    trace_id = get_trace_id(request)
    session_token = _extract_bearer_token(authorization)

    # Check session and get user_id
    session_data = await session_service.get_session(session_token, trace_id)
    user_id = session_data.user.id

    try:
        version = await article_service.get_article_version(article_id, version_id, user_id)
        return ArticleVersionResponse(**version)
    except ValueError as e:
        if "not found" in str(e):
            raise AppError(status.HTTP_404_NOT_FOUND, ErrorCode.NOT_FOUND) from None
        if "does not belong" in str(e):
            raise AppError(status.HTTP_400_BAD_REQUEST, ErrorCode.VALIDATION_ERROR) from None
        raise AppError(status.HTTP_400_BAD_REQUEST, ErrorCode.VALIDATION_ERROR) from None
    except PermissionError:
        raise AppError(status.HTTP_403_FORBIDDEN, ErrorCode.FORBIDDEN) from None


@router.delete(
    "/articles/{article_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=RESPONSES,
    summary="Delete an article",
)
async def delete_article(
    request: Request,
    article_id: UUID,
    article_service: Annotated[ArticleService, Depends(get_article_service)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
    authorization: Annotated[str | None, Header(description="Bearer session token")] = None,
) -> None:
    """Soft-delete an article. Only space owner or superadmin allowed."""
    trace_id = get_trace_id(request)
    session_token = _extract_bearer_token(authorization)

    session_data = await session_service.get_session(session_token, trace_id)
    user_id = session_data.user.id
    user_perm = session_data.user.permission

    try:
        await article_service.delete_article(article_id, user_id, user_perm)
        return
    except ValueError:
        raise AppError(status.HTTP_404_NOT_FOUND, ErrorCode.NOT_FOUND) from None
    except PermissionError:
        raise AppError(status.HTTP_403_FORBIDDEN, ErrorCode.FORBIDDEN) from None


def _extract_bearer_token(authorization: str | None) -> str:
    """Extracts bearer token from header."""
    if not authorization:
        raise AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.SESSION_MISSING)
    if not authorization.startswith("Bearer "):
        raise AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.SESSION_MISSING)
    return authorization[7:]
