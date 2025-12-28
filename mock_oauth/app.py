"""Local mock for oauth.name token issuing (dev only)."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import time

from Crypto.Cipher import AES
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI()

IV_LENGTH = 16
HMAC_LENGTH = 32
TOKEN_HEADER_LENGTH = IV_LENGTH + HMAC_LENGTH


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
    """Возвращает набор токенов для edge-cases (dev/test only)."""
    now = int(time.time())
    ttl_seconds = int(os.getenv("TOKEN_TTL_SECONDS", "86400"))
    fixed_created_at = _get_fixed_created_at()
    # Фиксированный IV нужен только для детерминированных токенов в dev/test.
    fixed_iv = b"\x00" * IV_LENGTH if fixed_created_at is not None else None
    base_payload = {
        "telegram_id": int(os.getenv("OAUTH_MOCK_TELEGRAM_ID", "123456")),
        "username": os.getenv("OAUTH_MOCK_USERNAME", "demo"),
        "first_name": os.getenv("OAUTH_MOCK_FIRST_NAME", "Demo"),
        "last_name": os.getenv("OAUTH_MOCK_LAST_NAME", "User"),
        "photo_url": os.getenv("OAUTH_MOCK_PHOTO_URL", "https://example.com/photo.png"),
        "permission": os.getenv("OAUTH_MOCK_PERMISSION", "admin"),
    }
    created_at = fixed_created_at if fixed_created_at is not None else now
    valid = dict(base_payload, created_at=created_at)
    expired = dict(base_payload, created_at=created_at - ttl_seconds - 1)
    # missing_fields: отсутствует telegram_id (валидация payload должна падать).
    missing_fields = dict(base_payload, created_at=created_at)
    missing_fields.pop("telegram_id", None)
    # wrong_types: telegram_id/created_at заданы строками.
    wrong_types = dict(base_payload, telegram_id="123", created_at="1690000000")

    valid_token = _encrypt_payload(valid, fixed_iv=fixed_iv)
    return {
        "valid": valid_token,
        "expired": _encrypt_payload(expired, fixed_iv=fixed_iv),
        "invalid": "invalid-token",
        # invalid_hmac: base64 валиден, но HMAC подпорчен.
        "invalid_hmac": _tamper_hmac(valid_token),
        "invalid_base64": "!!!not_base64!!!",
        "missing_fields": _encrypt_payload(missing_fields, fixed_iv=fixed_iv),
        "wrong_types": _encrypt_payload(wrong_types, fixed_iv=fixed_iv),
    }


def _encrypt_payload(payload: dict, *, fixed_iv: bytes | None = None) -> str:
    application_id = os.getenv("OAUTH_NAME_APPLICATION_ID", "local-app")
    secret_key = os.getenv("OAUTH_NAME_SECRET_KEY", "local-secret")
    private_key = f"{application_id}:{secret_key}"
    key = hashlib.sha256(private_key.encode()).digest()
    iv = fixed_iv or os.urandom(IV_LENGTH)
    plaintext = json.dumps(payload).encode()
    padded = _pkcs7_pad(plaintext)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    ciphertext = cipher.encrypt(padded)
    hash_value = hmac.new(key, ciphertext + iv, hashlib.sha256).digest()
    return base64.b64encode(iv + hash_value + ciphertext).decode()


def _pkcs7_pad(data: bytes, block_size: int = 16) -> bytes:
    pad_len = block_size - (len(data) % block_size)
    return data + bytes([pad_len]) * pad_len


def _tamper_hmac(token: str) -> str:
    """Портит 1 байт HMAC, сохраняя валидный base64."""
    try:
        raw = base64.b64decode(token, validate=True)
    except (binascii.Error, ValueError):
        return token
    if len(raw) <= TOKEN_HEADER_LENGTH:
        return token
    mutated = bytearray(raw)
    mutated[IV_LENGTH] ^= 0xFF
    return base64.b64encode(bytes(mutated)).decode()


def _get_fixed_created_at() -> int | None:
    """Читает фиксированный created_at для детерминированных токенов."""
    value = os.getenv("OAUTH_MOCK_FIXED_CREATED_AT")
    if value is None or not value.strip():
        return None
    return int(value)
