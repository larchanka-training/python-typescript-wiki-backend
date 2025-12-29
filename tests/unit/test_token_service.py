"""Unit tests for TokenService decryption and validation."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from Crypto.Cipher import AES
import pytest

from app.core.errors import AppError, ErrorCode
from app.services.token_service import TokenService

APPLICATION_ID = "app-id"
SECRET_KEY = "secret"  # noqa: S105


def _pkcs7_pad(data: bytes, block_size: int = 16) -> bytes:
    pad_len = block_size - (len(data) % block_size)
    return data + bytes([pad_len]) * pad_len


def _encrypt_payload(payload: dict, *, application_id: str, secret_key: str) -> str:
    key = hashlib.sha256(f"{application_id}:{secret_key}".encode()).digest()
    iv = b"\x00" * 16
    plaintext = json.dumps(payload).encode()
    cipher = AES.new(key, AES.MODE_CBC, iv)
    ciphertext = cipher.encrypt(_pkcs7_pad(plaintext))
    hash_value = hmac.new(key, ciphertext + iv, hashlib.sha256).digest()
    return base64.b64encode(iv + hash_value + ciphertext).decode()


def test_verify_token_valid() -> None:
    now = int(time.time())
    payload = {"telegram_id": 123, "username": "user", "created_at": now}
    token = _encrypt_payload(payload, application_id=APPLICATION_ID, secret_key=SECRET_KEY)

    service = TokenService(application_id=APPLICATION_ID, secret_key=SECRET_KEY, ttl_seconds=60)
    decoded = service.verify_token(token)

    assert decoded.telegram_id == 123
    assert decoded.username == "user"
    assert decoded.created_at == now


def test_verify_token_expired() -> None:
    now = int(time.time())
    payload = {"telegram_id": 123, "username": "user", "created_at": now - 120}
    token = _encrypt_payload(payload, application_id=APPLICATION_ID, secret_key=SECRET_KEY)

    service = TokenService(application_id=APPLICATION_ID, secret_key=SECRET_KEY, ttl_seconds=60)
    with pytest.raises(AppError) as exc_info:
        service.verify_token(token)

    assert exc_info.value.code == ErrorCode.OAUTH_CODE_INVALID


def test_verify_token_invalid_hmac() -> None:
    now = int(time.time())
    payload = {"telegram_id": 123, "username": "user", "created_at": now}
    token = _encrypt_payload(payload, application_id=APPLICATION_ID, secret_key=SECRET_KEY)
    tampered = token[:-2] + "AA"

    service = TokenService(application_id=APPLICATION_ID, secret_key=SECRET_KEY, ttl_seconds=60)
    with pytest.raises(AppError) as exc_info:
        service.verify_token(tampered)

    assert exc_info.value.code == ErrorCode.OAUTH_CODE_INVALID


def test_verify_token_invalid_payload() -> None:
    now = int(time.time())
    payload = {"telegram_id": "not-int", "username": "user", "created_at": now}
    token = _encrypt_payload(payload, application_id=APPLICATION_ID, secret_key=SECRET_KEY)

    service = TokenService(application_id=APPLICATION_ID, secret_key=SECRET_KEY, ttl_seconds=60)
    with pytest.raises(AppError) as exc_info:
        service.verify_token(token)

    assert exc_info.value.code == ErrorCode.OAUTH_CODE_INVALID
