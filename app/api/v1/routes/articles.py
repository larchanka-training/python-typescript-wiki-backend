"""API routes for articles.

All endpoints are nested under /spaces/{space_id}/articles to reflect the
resource hierarchy and simplify authorization.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, Query, Request, status

from app.api.deps import get_article_service, get_session_service
from app.api.v1.schemas.articles import (
    ArticleCreateRequest,
    ArticleCreateResponse,
    ArticleListItem,
    ArticleListResponse,
    ArticleSaveRequest,
    ArticleVersionResponse,
    ArticleSearchResponse,
)
from app.core.errors import AppError, ErrorCode, ErrorResponse
from app.core.trace import get_trace_id
from app.repositories.articles import ConflictError
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
    status.HTTP_409_CONFLICT: {
        "model": ErrorResponse,
        "description": "Version conflict (optimistic locking)",
        "content": {
            "application/json": {
                "examples": {
                    "version_conflict": {
                        "summary": "Version conflict",
                        "value": {
                            "status": "error",
                            "message": "ARTICLE_VERSION_CONFLICT",
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


# ── POST /spaces/{space_id}/articles ────────────────────────────────


@router.post(
    "/spaces/{space_id}/articles",
    response_model=ArticleCreateResponse,
    status_code=status.HTTP_201_CREATED,
    responses=RESPONSES,
    summary="Create a new article",
)
async def create_article(
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
    """
    trace_id = get_trace_id(request)
    session_token = _extract_bearer_token(authorization)

    session_data = await session_service.get_session(session_token, trace_id)
    user_id = session_data.user.id

    try:
        article_id = await article_service.create_article(
            space_id,
            body.title,
            body.content,
            user_id,
            show_toc=body.show_toc,
            parent_id=body.parent_id,
            position=body.position,
        )
        return ArticleCreateResponse(id=article_id)
    except ValueError:
        raise AppError(status.HTTP_404_NOT_FOUND, ErrorCode.NOT_FOUND) from None
    except PermissionError:
        raise AppError(status.HTTP_403_FORBIDDEN, ErrorCode.FORBIDDEN) from None


# ── GET /spaces/{space_id}/articles ─────────────────────────────────


@router.get(
    "/spaces/{space_id}/articles",
    response_model=ArticleListResponse,
    status_code=status.HTTP_200_OK,
    responses=RESPONSES,
    summary="List articles in a space",
)
async def list_articles(
    request: Request,
    space_id: UUID,
    article_service: Annotated[ArticleService, Depends(get_article_service)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
    parent_id: UUID | None = None,
    filter_by_parent: bool = False,
    authorization: Annotated[str | None, Header(description="Bearer session token")] = None,
) -> ArticleListResponse:
    """Lists articles in the specified space (supports lazy-loading filtering by parent_id)."""
    trace_id = get_trace_id(request)
    session_token = _extract_bearer_token(authorization)

    session_data = await session_service.get_session(session_token, trace_id)
    user_id = session_data.user.id
    user_perm = session_data.user.permission

    try:
        articles = await article_service.list_articles(space_id, user_id, user_perm, parent_id, filter_by_parent)
        return ArticleListResponse(
            articles=[ArticleListItem(**a) for a in articles],
        )
    except PermissionError:
        raise AppError(status.HTTP_403_FORBIDDEN, ErrorCode.FORBIDDEN) from None


@router.get(
    "/spaces/{space_id}/articles/{article_id}/path",
    response_model=ArticleListResponse,
    status_code=status.HTTP_200_OK,
    responses=RESPONSES,
    summary="Get path (ancestors) of an article",
)
async def get_article_path(
    request: Request,
    space_id: UUID,
    article_id: UUID,
    article_service: Annotated[ArticleService, Depends(get_article_service)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
    authorization: Annotated[str | None, Header(description="Bearer session token")] = None,
) -> ArticleListResponse:
    """Returns ancestors of an article to help expanding the tree sidebar."""
    trace_id = get_trace_id(request)
    session_token = _extract_bearer_token(authorization)

    session_data = await session_service.get_session(session_token, trace_id)
    user_id = session_data.user.id
    user_perm = session_data.user.permission

    try:
        ancestors = await article_service.get_article_path(space_id, article_id, user_id, user_perm)
        # Assuming ArticleListItem can handle partial model from ancestors if needed,
        # otherwise we might need a separate schema for path info.
        return ArticleListResponse(
            articles=[ArticleListItem(**a) for a in ancestors],
        )
    except PermissionError:
        raise AppError(status.HTTP_403_FORBIDDEN, ErrorCode.FORBIDDEN) from None


# ── GET /spaces/{space_id}/articles/{article_id} ────────────────────


@router.get(
    "/spaces/{space_id}/articles/{article_id}",
    response_model=ArticleVersionResponse,
    status_code=status.HTTP_200_OK,
    responses=RESPONSES,
    summary="Get the latest version of an article",
)
async def get_article(
    request: Request,
    space_id: UUID,
    article_id: UUID,
    article_service: Annotated[ArticleService, Depends(get_article_service)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
    authorization: Annotated[str | None, Header(description="Bearer session token")] = None,
) -> ArticleVersionResponse:
    """Gets the latest version of the specified article.

    User must have access to the space containing the article.
    """
    trace_id = get_trace_id(request)
    session_token = _extract_bearer_token(authorization)

    session_data = await session_service.get_session(session_token, trace_id)
    user_id = session_data.user.id
    user_perm = session_data.user.permission

    try:
        version = await article_service.get_latest_article_version(space_id, article_id, user_id, user_perm)
        return ArticleVersionResponse(**version)
    except ValueError:
        raise AppError(status.HTTP_404_NOT_FOUND, ErrorCode.NOT_FOUND) from None
    except PermissionError:
        raise AppError(status.HTTP_403_FORBIDDEN, ErrorCode.FORBIDDEN) from None


# ── PUT /spaces/{space_id}/articles/{article_id} ────────────────────


@router.put(
    "/spaces/{space_id}/articles/{article_id}",
    response_model=ArticleVersionResponse,
    status_code=status.HTTP_200_OK,
    responses=RESPONSES,
    summary="Save a new version of an article",
)
async def save_article_version(
    request: Request,
    space_id: UUID,
    article_id: UUID,
    article_service: Annotated[ArticleService, Depends(get_article_service)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
    body: Annotated[ArticleSaveRequest, Body()],
    authorization: Annotated[str | None, Header(description="Bearer session token")] = None,
) -> ArticleVersionResponse:
    """Saves a new version of an existing article.

    Only the space owner or superadmin may update.
    Supports optimistic locking via ``base_version_number``.
    Returns 409 ARTICLE_VERSION_CONFLICT on conflict.
    """
    trace_id = get_trace_id(request)
    session_token = _extract_bearer_token(authorization)

    session_data = await session_service.get_session(session_token, trace_id)
    user_id = session_data.user.id
    user_perm = session_data.user.permission

    try:
        version_id = await article_service.save_article_version(
            space_id,
            article_id,
            body.title,
            body.content,
            user_id,
            user_perm,
            show_toc=body.show_toc,
            content_format=body.content_format,
            change_summary=body.change_summary,
            base_version_number=body.base_version_number,
        )
        # Return the newly created version
        version = await article_service.get_latest_article_version(space_id, article_id, user_id, user_perm)
        return ArticleVersionResponse(**version)
    except ValueError:
        raise AppError(status.HTTP_404_NOT_FOUND, ErrorCode.NOT_FOUND) from None
    except PermissionError:
        raise AppError(status.HTTP_403_FORBIDDEN, ErrorCode.FORBIDDEN) from None
    except ConflictError:
        raise AppError(status.HTTP_409_CONFLICT, ErrorCode.ARTICLE_VERSION_CONFLICT) from None


# ── POST /spaces/{space_id}/articles/{article_id}/lock ─────────────


@router.post(
    "/spaces/{space_id}/articles/{article_id}/lock",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=RESPONSES,
    summary="Lock an article",
)
async def lock_article(
    request: Request,
    space_id: UUID,
    article_id: UUID,
    article_service: Annotated[ArticleService, Depends(get_article_service)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
    authorization: Annotated[str | None, Header(description="Bearer session token")] = None,
) -> None:
    """Locks an article to prevent editing. Only space owner or superadmin allowed."""
    trace_id = get_trace_id(request)
    session_token = _extract_bearer_token(authorization)

    session_data = await session_service.get_session(session_token, trace_id)
    user_id = session_data.user.id
    user_perm = session_data.user.permission

    try:
        await article_service.lock_article(space_id, article_id, user_id, user_perm)
    except ValueError:
        raise AppError(status.HTTP_404_NOT_FOUND, ErrorCode.NOT_FOUND) from None
    except PermissionError:
        raise AppError(status.HTTP_403_FORBIDDEN, ErrorCode.FORBIDDEN) from None


# ── POST /spaces/{space_id}/articles/{article_id}/unlock ───────────


@router.post(
    "/spaces/{space_id}/articles/{article_id}/unlock",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=RESPONSES,
    summary="Unlock an article",
)
async def unlock_article(
    request: Request,
    space_id: UUID,
    article_id: UUID,
    article_service: Annotated[ArticleService, Depends(get_article_service)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
    authorization: Annotated[str | None, Header(description="Bearer session token")] = None,
) -> None:
    """Unlocks a previously locked article. Only space owner or superadmin allowed."""
    trace_id = get_trace_id(request)
    session_token = _extract_bearer_token(authorization)

    session_data = await session_service.get_session(session_token, trace_id)
    user_id = session_data.user.id
    user_perm = session_data.user.permission

    try:
        await article_service.unlock_article(space_id, article_id, user_id, user_perm)
    except ValueError:
        raise AppError(status.HTTP_404_NOT_FOUND, ErrorCode.NOT_FOUND) from None
    except PermissionError:
        raise AppError(status.HTTP_403_FORBIDDEN, ErrorCode.FORBIDDEN) from None


# ── DELETE /spaces/{space_id}/articles/{article_id} ─────────────────


@router.delete(
    "/spaces/{space_id}/articles/{article_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=RESPONSES,
    summary="Soft-delete an article",
)
async def delete_article(
    request: Request,
    space_id: UUID,
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
        await article_service.delete_article(space_id, article_id, user_id, user_perm)
    except ValueError:
        raise AppError(status.HTTP_404_NOT_FOUND, ErrorCode.NOT_FOUND) from None
    except PermissionError:
        raise AppError(status.HTTP_403_FORBIDDEN, ErrorCode.FORBIDDEN) from None


# ── GET /spaces/{space_id}/articles/{article_id}/versions ───────────


@router.get(
    "/spaces/{space_id}/articles/{article_id}/versions",
    response_model=list[ArticleVersionResponse],
    status_code=status.HTTP_200_OK,
    responses=RESPONSES,
    summary="Get all versions of an article",
)
async def get_article_versions(
    request: Request,
    space_id: UUID,
    article_id: UUID,
    article_service: Annotated[ArticleService, Depends(get_article_service)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
    authorization: Annotated[str | None, Header(description="Bearer session token")] = None,
) -> list[ArticleVersionResponse]:
    """Gets all versions of the specified article.

    User must have access to the space containing the article.
    """
    trace_id = get_trace_id(request)
    session_token = _extract_bearer_token(authorization)

    session_data = await session_service.get_session(session_token, trace_id)
    user_id = session_data.user.id
    user_perm = session_data.user.permission

    try:
        versions = await article_service.get_article_versions(space_id, article_id, user_id, user_perm)
        return [ArticleVersionResponse(**v) for v in versions]
    except ValueError:
        raise AppError(status.HTTP_404_NOT_FOUND, ErrorCode.NOT_FOUND) from None
    except PermissionError:
        raise AppError(status.HTTP_403_FORBIDDEN, ErrorCode.FORBIDDEN) from None


# ── GET /spaces/{space_id}/articles/{article_id}/versions/{version_number}


@router.get(
    "/spaces/{space_id}/articles/{article_id}/versions/{version_number}",
    response_model=ArticleVersionResponse,
    status_code=status.HTTP_200_OK,
    responses=RESPONSES,
    summary="Get a specific version of an article by version number",
)
async def get_article_version(
    request: Request,
    space_id: UUID,
    article_id: UUID,
    version_number: int,
    article_service: Annotated[ArticleService, Depends(get_article_service)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
    authorization: Annotated[str | None, Header(description="Bearer session token")] = None,
) -> ArticleVersionResponse:
    """Gets the specified version of an article by its ordinal number.

    User must have access to the space containing the article.
    """
    trace_id = get_trace_id(request)
    session_token = _extract_bearer_token(authorization)

    session_data = await session_service.get_session(session_token, trace_id)
    user_id = session_data.user.id
    user_perm = session_data.user.permission

    try:
        version = await article_service.get_article_version_by_number(
            space_id, article_id, version_number, user_id, user_perm,
        )
        return ArticleVersionResponse(**version)
    except ValueError:
        raise AppError(status.HTTP_404_NOT_FOUND, ErrorCode.NOT_FOUND) from None
    except PermissionError:
        raise AppError(status.HTTP_403_FORBIDDEN, ErrorCode.FORBIDDEN) from None


@router.get(
    "/articles/recent",
    response_model=ArticleListResponse,
    status_code=status.HTTP_200_OK,
    responses=RESPONSES,
    summary="List recently touched articles across all spaces",
)
async def get_recent_articles(
    request: Request,
    article_service: Annotated[ArticleService, Depends(get_article_service)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
    limit: int = 10,
    authorization: Annotated[str | None, Header(description="Bearer session token")] = None,
) -> ArticleListResponse:
    """Returns articles the user recently edited or created."""
    trace_id = get_trace_id(request)
    session_token = _extract_bearer_token(authorization)

    session_data = await session_service.get_session(session_token, trace_id)
    user_id = session_data.user.id

    articles = await article_service.get_recent_articles(user_id, limit)
    return ArticleListResponse(
        articles=[ArticleListItem(**a) for a in articles],
    )


@router.get(
    "/articles/search",
    response_model=ArticleSearchResponse,
    status_code=status.HTTP_200_OK,
    responses=RESPONSES,
    summary="Global search across all articles the user has access to",
)
async def search_articles(
    request: Request,
    article_service: Annotated[ArticleService, Depends(get_article_service)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
    q: Annotated[str, Query(min_length=3, max_length=64)],
    limit: Annotated[int, Query(gt=0, le=100)] = 20,
    authorization: Annotated[str | None, Header(description="Bearer session token")] = None,
) -> ArticleSearchResponse:
    """Searches articles by title and content.

    Requires session authentication via Bearer token.
    Possible statuses: 200 OK; 400 VALIDATION_ERROR; 401 SESSION_MISSING/SESSION_EXPIRED;
    500 INTERNAL_ERROR.
    """
    trace_id = get_trace_id(request)
    session_token = _extract_bearer_token(authorization)

    session_data = await session_service.get_session(session_token, trace_id)
    user_id = session_data.user.id

    articles = await article_service.search_articles(user_id, q, limit)
    return ArticleSearchResponse(
        articles=[ArticleListItem(**a) for a in articles],
    )


# ── helpers ─────────────────────────────────────────────────────────


def _extract_bearer_token(authorization: str | None) -> str:
    """Extracts bearer token from header."""
    if not authorization:
        raise AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.SESSION_MISSING)
    if not authorization.startswith("Bearer "):
        raise AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.SESSION_MISSING)
    return authorization[7:]
