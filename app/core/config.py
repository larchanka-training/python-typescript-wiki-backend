"""Application settings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
import os

from .environment import Environment


@dataclass(frozen=True)
class Settings:
    """Настройки приложения, загружаемые из env."""

    oauth_name_application_id: str
    oauth_name_secret_key: str
    token_ttl_seconds: int
    session_ttl_seconds: int
    environment: Environment
    test_access_token: str | None
    cors_origins: list[str]


def _env_optional(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def _env_required(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        msg = f"Missing required environment variable: {name}"
        raise RuntimeError(msg)
    return value.strip()


def _env_int_required(name: str) -> int:
    value = _env_required(name)
    try:
        return int(value)
    except ValueError as exc:
        msg = f"Invalid integer for {name}"
        raise RuntimeError(msg) from exc


def _env_enum_required(name: str, enum_cls: type[Enum]) -> Enum:
    value = _env_required(name)
    try:
        return enum_cls(value.lower())
    except ValueError as exc:
        msg = f"Invalid value for {name}: {value}"
        raise RuntimeError(msg) from exc
    

def _env_enum_optional(name: str, enum_cls: type[Enum], default: Enum) -> Enum:
    value = _env_optional(name)
    if value is None:
        return default
    try:
        return enum_cls(value.lower())
    except ValueError as exc:
        msg = f"Invalid value for {name}: {value}"
        raise RuntimeError(msg) from exc


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # TTL значения задаются в секундах через переменные окружения.
    return Settings(
        oauth_name_application_id=_env_required("OAUTH_NAME_APPLICATION_ID"),
        oauth_name_secret_key=_env_required("OAUTH_NAME_SECRET_KEY"),
        token_ttl_seconds=_env_int_required("TOKEN_TTL_SECONDS"),
        session_ttl_seconds=_env_int_required("SESSION_TTL_SECONDS"),
        environment=_env_enum_optional("ENVIRONMENT", Environment, Environment.DEVELOPMENT),
        test_access_token=_env_optional("TEST_ACCESS_TOKEN"),
        cors_origins=[
            origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",")
        ],
    )
