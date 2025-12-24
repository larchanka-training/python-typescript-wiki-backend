"""Local mock for oauth.name token issuing (dev only)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

from Crypto.Cipher import AES
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI()


class IssueTokenRequest(BaseModel):
    """Payload for issuing a token in local mock."""

    telegram_id: int = Field(..., examples=[123456])
    username: str | None = Field(default=None, examples=["demo"])
    first_name: str | None = Field(default=None, examples=["Demo"])
    last_name: str | None = Field(default=None, examples=["User"])
    photo_url: str | None = Field(default=None, examples=["https://example.com/photo.png"])
    permission: str | None = Field(default=None, examples=["admin"])
    created_at: int | None = Field(default=None, examples=[1700000000])


@app.post("/oauth/token/issue")
async def issue_token(payload: IssueTokenRequest) -> dict[str, str]:
    """Issue an encrypted token using oauth.name rules (dev only)."""
    data = payload.model_dump()
    data["created_at"] = data["created_at"] or int(time.time())
    return {"token": _encrypt_payload(data)}


@app.get("/oauth/token/examples")
async def token_examples() -> dict[str, str]:
    """Return example valid/expired/invalid tokens for local testing."""
    now = int(time.time())
    ttl_seconds = int(os.getenv("TOKEN_TTL_SECONDS", "86400"))
    base_payload = {
        "telegram_id": int(os.getenv("OAUTH_MOCK_TELEGRAM_ID", "123456")),
        "username": os.getenv("OAUTH_MOCK_USERNAME", "demo"),
        "first_name": os.getenv("OAUTH_MOCK_FIRST_NAME", "Demo"),
        "last_name": os.getenv("OAUTH_MOCK_LAST_NAME", "User"),
        "photo_url": os.getenv("OAUTH_MOCK_PHOTO_URL", "https://example.com/photo.png"),
        "permission": os.getenv("OAUTH_MOCK_PERMISSION", "admin"),
    }
    valid = dict(base_payload, created_at=now)
    expired = dict(base_payload, created_at=now - ttl_seconds - 1)
    return {
        "valid": _encrypt_payload(valid),
        "expired": _encrypt_payload(expired),
        "invalid": "invalid-token",
    }


def _encrypt_payload(payload: dict) -> str:
    application_id = os.getenv("OAUTH_NAME_APPLICATION_ID", "local-app")
    secret_key = os.getenv("OAUTH_NAME_SECRET_KEY", "local-secret")
    private_key = f"{application_id}:{secret_key}"
    key = hashlib.sha256(private_key.encode()).digest()
    iv = os.urandom(16)
    plaintext = json.dumps(payload).encode()
    padded = _pkcs7_pad(plaintext)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    ciphertext = cipher.encrypt(padded)
    hash_value = hmac.new(key, ciphertext + iv, hashlib.sha256).digest()
    return base64.b64encode(iv + hash_value + ciphertext).decode()


def _pkcs7_pad(data: bytes, block_size: int = 16) -> bytes:
    pad_len = block_size - (len(data) % block_size)
    return data + bytes([pad_len]) * pad_len
