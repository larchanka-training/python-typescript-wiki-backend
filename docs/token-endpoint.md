# Token Verification Endpoint (/token)

## Краткое описание
Документ описывает реализацию `POST /token` (без префикса `/api/v1`): локальная расшифровка токена oauth.name, проверка TTL, upsert пользователя и единый формат ошибок. Содержит список изменённых файлов и инструкции для локальной проверки.

## Оглавление
- [Что сделано](#что-сделано)
- [Архитектура и поток запроса](#архитектура-и-поток-запроса)
- [Контракт API](#контракт-api)
- [Конфигурация](#конфигурация)
- [Миграции](#миграции)
- [Как тестировать](#как-тестировать)
- [Безопасность](#безопасность)
- [Known limitations / TODO](#known-limitations--todo)

## Что сделано
- Реализован endpoint `POST /token` и Pydantic схемы: `app/api/v1/routes/auth.py`, `app/api/v1/schemas/auth.py`.
- Добавлен `TokenService` (AES-256-CBC + HMAC + PKCS#7 + TTL): `app/services/token_service.py`.
- Обновлён сервис upsert и модель пользователя: `app/services/auth_service.py`, `app/services/models.py`, `app/repositories/users.py`, `app/models.py`.
- Введён единый формат ошибок `{status,message,timestamp}` и enum кодов: `app/core/errors.py`.
- Конфигурация и env-переменные: `app/core/config.py`, `.env.example`, `docker-compose.yml`, `docker-compose.mock.yml`.
- Добавлена миграция `last_login_at` и `username` nullable: `alembic/versions/0003_add_last_login_at.py`.
- Локальный mock issuer токенов (dev/test-only): `mock_oauth/app.py`.
- Тесты: `tests/unit/test_token_service.py`, `tests/integration/test_token_verify.py`.
- Обновлена документация: `docs/Архитектура бэкенда.md`, `docs/Миграции.md`, `docs/Формат ошибок.md` (source of truth), `docs/errors.md` (дубликат), `docs/project-structure.md`, `README.md`.

## Архитектура и поток запроса
1) `POST /token` принимает JSON `{ "token": "..." }`.
2) `TokenService` расшифровывает токен:
   - base64 decode → `iv(16) + hmac(32) + ciphertext`;
   - HMAC SHA-256 в constant-time;
   - AES-256-CBC decrypt + PKCS#7 unpad;
   - plaintext парсится как JSON или JWT payload.
   Примечание: порядок/размеры `iv/hmac/ciphertext` взяты из документации oauth.name и приложенного Python3 примера. Алгоритм не менять.
3) Валидация payload: `telegram_id` (int), `created_at` (unix int), `username` (optional).
4) TTL: `now - created_at > TOKEN_TTL_SECONDS` → 401 `OAUTH_CODE_INVALID`.
5) Upsert пользователя по `telegram_id`, `last_login_at = now()`.
6) Ответ: `200 OK` + `{ created, user }`.

## Контракт API

### Request
Фактический путь: `POST /token` (префикса `/api/v1` нет).

```json
{
  "token": "BASE64_ENCRYPTED_TOKEN"
}
```

### Response 200
```json
{
  "created": true,
  "user": {
    "telegram_id": 123456,
    "username": "user",
    "created_at": "2024-01-01T12:00:00Z",
    "last_login_at": "2024-01-01T12:00:00Z"
  }
}
```
`created_at` и `last_login_at` — это timestamps из БД в формате ISO 8601. `created_at` из токена используется только для TTL и не возвращается в ответе.

### Ошибки (единый формат)
```json
{
  "status": "error",
  "message": "OAUTH_CODE_INVALID",
  "timestamp": "2025-01-01T12:00:00Z"
}
```

Таблица веток:

| Ветка | HTTP | message |
| --- | --- | --- |
| Токен отсутствует/пустой/не строка/не JSON | 400 | VALIDATION_ERROR |
| Крипто-проверка/парсинг/TTL не прошли | 401 | OAUTH_CODE_INVALID |
| Ошибка БД/непредвиденная ошибка | 500 | INTERNAL_ERROR |

## Конфигурация
ENV-переменные:
- `DATABASE_URL`
- `OAUTH_NAME_APPLICATION_ID`
- `OAUTH_NAME_SECRET_KEY`
- `TOKEN_TTL_SECONDS`
- `SESSION_TTL_SECONDS` (используется эндпойнтами `/session*`)

Docker compose:
- `docker-compose.yml` — API + DB.
- `docker-compose.mock.yml` — dev/test-only mock issuer токенов (не используется в проде).

Порты:
- API: `localhost:8000`
- DB: `localhost:5433` (контейнер `5432`)
- Mock issuer: `localhost:9001` (dev/test-only)

## Миграции
Изменения:
- добавлен `last_login_at`;
- `username` стал nullable.

Применение:
```bash
alembic upgrade head
```

## Как тестировать

### Prerequisites
- Python 3.x и pip (для локального запуска без Docker).
- Docker + Docker Compose (для запуска через compose).
- ENV-переменные из раздела “Конфигурация”.
- Зависимость `pycryptodome` используется в `app/services/token_service.py` и `mock_oauth/app.py`.

### Локально через Docker
1) Запуск сервисов:
```bash
docker compose -f docker-compose.yml -f docker-compose.mock.yml up --build
```
2) Получить тестовые токены:
```bash
curl http://localhost:9001/oauth/token/examples
```
Возвращает ключи:
- `valid` → 200 (happy path)
- `expired` → 401 `OAUTH_CODE_INVALID`
- `invalid` → 401 `OAUTH_CODE_INVALID` (токен не проходит крипто/парсинг)
3) Проверить endpoint:
```bash
curl -X POST http://localhost:8000/token \
  -H "Content-Type: application/json" \
  -d '{"token":"<valid_token>"}'
```

### Локально без Docker
1) Установить зависимости:
```bash
pip install -r requirements.txt
```
2) Применить миграции:
```bash
alembic upgrade head
```
3) Запустить API:
```bash
export DATABASE_URL="<DATABASE_URL>"
export OAUTH_NAME_APPLICATION_ID="<APPLICATION_ID>"
export OAUTH_NAME_SECRET_KEY="<SECRET_KEY>"
export TOKEN_TTL_SECONDS="<SECONDS>"
fastapi dev app/main.py --host 0.0.0.0 --port 8000
```
4) При необходимости запустить mock issuer отдельно:
```bash
fastapi dev mock_oauth/app.py --host 0.0.0.0 --port 9001
```

### Pytest
```bash
pytest -q
```
Проверяет: валидные токены, TTL, HMAC, 400/401/500.

### Ручная проверка (curl)
```bash
curl -X POST http://localhost:8000/token \
  -H "Content-Type: application/json" \
  -d '{"token":"<token>"}'
```

### Негативные кейсы
- 400: отправить пустой токен `{"token": ""}`.
- 401: использовать `invalid-token` из `/oauth/token/examples`.
- 500: остановить контейнер `db` и повторить запрос.

## Безопасность
- Токен целиком не логируется; допускается только безопасный fingerprint.
- Ключи и TTL хранятся только в ENV (`.env.example`).
- Mock issuer — dev/test-only: подключается отдельным compose-файлом и не используется в проде.

## Known limitations / TODO
- В проекте есть дубликат документации по ошибкам: `docs/Формат ошибок.md` (source of truth) и `docs/errors.md`. План: объединить в одном файле и обновить ссылки в README.
- Связанные эндпойнты сессий: см. `docs/session-endpoints.md`.
