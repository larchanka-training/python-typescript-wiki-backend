# ruff: noqa: RUF002
"""FastAPI зависимости."""

from __future__ import annotations

from typing import Annotated

import asyncpg  # noqa: TC002
from fastapi import Depends

from app.core.config import get_settings
from app.db import get_connection
from app.repositories.articles import ArticleRepository, ArticleVersionRepository
from app.repositories.sessions import SessionRepository
from app.repositories.spaces import SpaceRepository
from app.repositories.users import UserRepository
from app.services.article_service import ArticleService
from app.services.auth_service import AuthService
from app.services.session_service import SessionService
from app.services.space_service import SpaceService
from app.services.token_service import TokenService
from app.services.user_service import UserService


def get_token_service() -> TokenService:
    """Создаёт TokenService с ключами oauth.name и TTL из env."""
    settings = get_settings()
    return TokenService(
        application_id=settings.oauth_name_application_id,
        secret_key=settings.oauth_name_secret_key,
        ttl_seconds=settings.token_ttl_seconds,
    )


def get_user_repository(
    connection: Annotated[asyncpg.Connection, Depends(get_connection)],
) -> UserRepository:
    """Создаёт UserRepository для текущего подключения БД."""
    return UserRepository(connection)


def get_auth_service(
    token_service: Annotated[TokenService, Depends(get_token_service)],
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> AuthService:
    """Создаёт AuthService из TokenService и UserRepository."""
    return AuthService(token_service, user_repository)


def get_session_repository(
    connection: Annotated[asyncpg.Connection, Depends(get_connection)],
) -> SessionRepository:
    """Создаёт SessionRepository для текущего подключения БД."""
    return SessionRepository(connection)


def get_session_service(
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
    session_repository: Annotated[SessionRepository, Depends(get_session_repository)],
) -> SessionService:
    """Создаёт SessionService из auth, репозиториев и конфигурации."""
    settings = get_settings()
    return SessionService(
        auth_service=auth_service,
        user_repository=user_repository,
        session_repository=session_repository,
        ttl_seconds=settings.session_ttl_seconds,
    )


def get_space_repository(
    connection: Annotated[asyncpg.Connection, Depends(get_connection)],
) -> SpaceRepository:
    """Создаёт SpaceRepository для текущего подключения БД."""
    return SpaceRepository(connection)


def get_space_service(
    space_repository: Annotated[SpaceRepository, Depends(get_space_repository)],
) -> SpaceService:
    """Создаёт SpaceService."""
    return SpaceService(space_repository)


def get_article_repository(
    connection: Annotated[asyncpg.Connection, Depends(get_connection)],
) -> ArticleRepository:
    """Создаёт ArticleRepository для текущего подключения БД."""
    return ArticleRepository(connection)


def get_article_version_repository(
    connection: Annotated[asyncpg.Connection, Depends(get_connection)],
) -> ArticleVersionRepository:
    """Создаёт ArticleVersionRepository для текущего подключения БД."""
    return ArticleVersionRepository(connection)


def get_article_service(
    article_repository: Annotated[ArticleRepository, Depends(get_article_repository)],
    article_version_repository: Annotated[ArticleVersionRepository, Depends(get_article_version_repository)],
    space_repository: Annotated[SpaceRepository, Depends(get_space_repository)],
) -> ArticleService:
    """Создаёт ArticleService."""
    return ArticleService(article_repository, article_version_repository, space_repository)


def get_user_service(
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserService:
    """Создаёт UserService."""
    return UserService(user_repository)
