"""Pytest configuration."""

from __future__ import annotations

from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load .env.local for test execution
# This ensures tests use the correct database URL, test token, and environment settings
env_file = ROOT / ".env.local"
if env_file.exists():
    load_dotenv(env_file, override=True)

# Provide fallback defaults for mandatory settings to allow tests to run without .env
import os
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("OAUTH_NAME_APPLICATION_ID", "test-id")
os.environ.setdefault("OAUTH_NAME_SECRET_KEY", "test-secret")
os.environ.setdefault("TOKEN_TTL_SECONDS", "3600")
os.environ.setdefault("SESSION_TTL_SECONDS", "86400")
os.environ.setdefault("CORS_ORIGINS", "*")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
