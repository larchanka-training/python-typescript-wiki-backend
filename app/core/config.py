"""Application settings."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os


@dataclass(frozen=True)
class Settings:
    """Настройки приложения, загружаемые из env."""

    oauth_name_application_id: str
    oauth_name_secret_key: str
    token_ttl_seconds: int
    session_ttl_seconds: int


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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # TTL значения задаются в секундах через переменные окружения.
    return Settings(
        oauth_name_application_id=_env_required("OAUTH_NAME_APPLICATION_ID"),
        oauth_name_secret_key=_env_required("OAUTH_NAME_SECRET_KEY"),
        token_ttl_seconds=_env_int_required("TOKEN_TTL_SECONDS"),
        session_ttl_seconds=_env_int_required("SESSION_TTL_SECONDS"),
    )
