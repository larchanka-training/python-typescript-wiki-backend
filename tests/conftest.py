"""Pytest configuration."""

from __future__ import annotations

from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load .env.development for test execution
# This ensures tests use the correct database URL, test token, and environment settings
env_file = ROOT / ".env.development"
if env_file.exists():
    load_dotenv(env_file, override=True)
