"""Логика дешифровки и проверки access token oauth.name."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging
import time
from typing import Any

from Crypto.Cipher import AES
from pydantic import BaseModel, ConfigDict, ValidationError

from app.core.environment import Environment
from app.core.errors import AppError, ErrorCode

logger = logging.getLogger(__name__)

_IV_LENGTH = 16
_HMAC_LENGTH = 32
_JWT_DOT_COUNT = 2


class TokenPayload(BaseModel):
    """Payload токена после дешифрования (структура по oauth.name)."""

    model_config = ConfigDict(strict=True)

    telegram_id: int
    username: str | None
    created_at: int
    first_name: str | None = None
    last_name: str | None = None
    photo_url: str | None = None
    permission: str | None = None


class TokenService:
    """Дешифрует и валидирует access token по спецификации oauth.name.

    Алгоритм и порядок операций соответствуют docs/oauth.name и приложенному Python3 примеру:
    base64 -> iv/hmac/ciphertext -> HMAC compare -> AES-256-CBC -> PKCS#7 -> JSON/JWT.
    
    В dev режиме поддерживает тестовые токены через verify_test_token().
    """

    def __init__(self, *, application_id: str, secret_key: str, ttl_seconds: int, environment: Environment | str = "production", test_token: str | None = None) -> None:
        private_key = f"{application_id}:{secret_key}"
        self._key = hashlib.sha256(private_key.encode()).digest()
        self._ttl_seconds = ttl_seconds
        self._environment = environment
        self._test_token = test_token

    def verify_token(self, token: str, trace_id: str | None = None) -> TokenPayload:
        """Дешифрует, парсит и валидирует токен.

        Ошибки криптографии/формата/TTL возвращают OAUTH_CODE_INVALID.
        """
        _ = trace_id
        # Никогда не логируем raw token; при необходимости — только безопасный fingerprint.
        payload = self._decrypt(token)
        try:
            data = TokenPayload.model_validate(payload)
        except ValidationError as exc:
            logger.info("token payload validation failed: trace_id=%s", trace_id)
            raise AppError(401, ErrorCode.OAUTH_CODE_INVALID) from exc

        now = int(time.time())
        # TTL считается по created_at из токена (unix timestamp, UTC).
        if now - data.created_at > self._ttl_seconds:
            raise AppError(401, ErrorCode.OAUTH_CODE_INVALID)
        return data

    def verify_test_token(self, token: str, trace_id: str | None = None) -> TokenPayload:
        """Валидирует тестовый токен только в dev режиме.
        
        Используется для интеграционных тестов. Возвращает фиксированный профиль тестового пользователя.
        """
        _ = trace_id
        if self._environment != Environment.DEVELOPMENT or not self._test_token:
            raise AppError(401, ErrorCode.OAUTH_CODE_INVALID)
        
        if token != self._test_token:
            raise AppError(401, ErrorCode.OAUTH_CODE_INVALID)
        
        # Возвращаем фиксированный профиль тестового пользователя
        now = int(time.time())
        return TokenPayload(
            telegram_id=9999999,
            username="test_user",
            created_at=now,
            first_name="Test",
            last_name="User",
            photo_url=None,
            permission=None,
        )

    def _decrypt(self, token: str) -> dict[str, Any]:
        raw = _b64decode(token)
        # Формат токена: iv(16) + hmac(32) + ciphertext (см. oauth.name docs/пример).
        if len(raw) <= _IV_LENGTH + _HMAC_LENGTH:
            raise AppError(401, ErrorCode.OAUTH_CODE_INVALID)

        iv = raw[:_IV_LENGTH]
        expected_hash = raw[_IV_LENGTH : _IV_LENGTH + _HMAC_LENGTH]
        ciphertext = raw[_IV_LENGTH + _HMAC_LENGTH :]

        computed_hash = hmac.new(self._key, ciphertext + iv, hashlib.sha256).digest()
        # Сравнение HMAC в constant-time для защиты от timing атак.
        if not hmac.compare_digest(computed_hash, expected_hash):
            raise AppError(401, ErrorCode.OAUTH_CODE_INVALID)

        cipher = AES.new(self._key, AES.MODE_CBC, iv)
        # AES-256-CBC + PKCS#7 unpad, затем decode UTF-8.
        padded = cipher.decrypt(ciphertext)
        plaintext = _pkcs7_unpad(padded)

        try:
            text = plaintext.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AppError(401, ErrorCode.OAUTH_CODE_INVALID) from exc

        payload = _parse_payload(text)
        if not isinstance(payload, dict):
            raise AppError(401, ErrorCode.OAUTH_CODE_INVALID)
        return payload


def _b64decode(token: str) -> bytes:
    cleaned = token.strip()
    # base64 может быть urlsafe; используем fallback с padding.  # noqa: RUF003
    try:
        return base64.b64decode(cleaned, validate=True)
    except (binascii.Error, ValueError):
        try:
            return base64.urlsafe_b64decode(_pad_b64(cleaned))
        except (binascii.Error, ValueError) as exc:
            raise AppError(401, ErrorCode.OAUTH_CODE_INVALID) from exc


def _pad_b64(value: str) -> str:
    return value + "=" * (-len(value) % 4)


def _pkcs7_unpad(data: bytes) -> bytes:
    # PKCS#7 padding проверяется строго, иначе токен считается невалидным.
    if not data:
        raise AppError(401, ErrorCode.OAUTH_CODE_INVALID)
    pad_len = data[-1]
    if pad_len < 1 or pad_len > _IV_LENGTH:
        raise AppError(401, ErrorCode.OAUTH_CODE_INVALID)
    if data[-pad_len:] != bytes([pad_len]) * pad_len:
        raise AppError(401, ErrorCode.OAUTH_CODE_INVALID)
    return data[:-pad_len]


def _parse_payload(text: str) -> dict[str, Any]:
    # Payload может быть JSON или JWT (payload = middle segment).
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    if text.count(".") == _JWT_DOT_COUNT:
        try:
            _, payload_segment, _ = text.split(".", 2)
            decoded = base64.urlsafe_b64decode(_pad_b64(payload_segment))
            return json.loads(decoded)
        except (binascii.Error, ValueError, json.JSONDecodeError) as exc:
            raise AppError(401, ErrorCode.OAUTH_CODE_INVALID) from exc

    raise AppError(401, ErrorCode.OAUTH_CODE_INVALID)
