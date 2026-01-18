"""Application environment enumeration."""

from __future__ import annotations

from enum import Enum


class Environment(str, Enum):
    """Application environment."""

    DEVELOPMENT = "development"
    PRODUCTION = "production"
