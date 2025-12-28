# E2E тестирование /token и /session* в Docker

## Краткое описание
Документ фиксирует полный E2E прогон в Docker для:
- `POST /token` (oauth.name decrypt + TTL + upsert users);
- `/session*` (stateful sessions: create/check/refresh/logout).

Инструкция рассчитана на повторяемость без доступа к прод-окружению.

## Оглавление
- [Preconditions / Требования](#preconditions--требования)
- [Bring-up](#bring-up)
- [DB checks](#db-checks)
- [E2E: Token A–F](#e2e-token-af)
- [E2E: Session S1–S6](#e2e-session-s1s6)
- [Contract checks](#contract-checks)
- [Security checks](#security-checks)
- [Troubleshooting](#troubleshooting)
- [Result](#result)

## Preconditions / Требования
- Docker и Docker Compose.
- Порты:
  - API: `localhost:8000`
  - DB: `localhost:5433` (контейнер `5432`)
  - Mock issuer: `localhost:9001` (dev/test-only)
- Compose файлы:
  - `docker-compose.yml` — API + DB.
  - `docker-compose.mock.yml` — dev/test-only mock issuer токенов. Не используйте в проде.
- ENV переменные (без значений):
  - `DATABASE_URL`
  - `OAUTH_NAME_APPLICATION_ID`
  - `OAUTH_NAME_SECRET_KEY`
  - `TOKEN_TTL_SECONDS`
  - `SESSION_TTL_SECONDS`

## Bring-up
```bash
docker compose -f docker-compose.yml -f docker-compose.mock.yml up --build -d
docker compose -f docker-compose.yml -f docker-compose.mock.yml ps
```

## DB checks
Проверка схемы пользователей:
```bash
docker compose -f docker-compose.yml -f docker-compose.mock.yml exec -T db \
  psql -U postgres -d postgres -c "\d users"
```
Ожидаемо: есть `telegram_id`, `last_login_at`.

Проверка схемы сессий:
```bash
docker compose -f docker-compose.yml -f docker-compose.mock.yml exec -T db \
  psql -U postgres -d postgres -c "\d sessions"
```
Ожидаемо: `token_hash`, `expires_at`, `revoked_at`, индексы по `user_id` и `expires_at`.

## E2E: Token A–F

### A) Получение примеров токенов (/oauth/token/examples)
```bash
curl http://localhost:9001/oauth/token/examples
```
Ожидаемо: ключи `valid`, `expired`, `invalid`.

### B) Happy path (created true/false, last_login_at update, username update)
1) Сгенерировать токен:
```bash
curl -X POST http://localhost:9001/oauth/token/issue \
  -H "Content-Type: application/json" \
  -d '{"telegram_id":123456,"username":"first"}'
```

2) Первый вызов `/token`:
```bash
curl -X POST http://localhost:8000/token \
  -H "Content-Type: application/json" \
  -d '{"token":"<token>"}'
```
Ожидаемо: `200`, `created=true`.

3) Повторный вызов `/token`:
```bash
curl -X POST http://localhost:8000/token \
  -H "Content-Type: application/json" \
  -d '{"token":"<token>"}'
```
Ожидаемо: `200`, `created=false`, `last_login_at` обновлён.

4) Обновление username:
```bash
curl -X POST http://localhost:9001/oauth/token/issue \
  -H "Content-Type: application/json" \
  -d '{"telegram_id":123456,"username":"second"}'
```
Повторить запрос `/token` — ожидание: `user.username="second"`.

### C) Validation (400 VALIDATION_ERROR, без 422)
```bash
curl -X POST http://localhost:8000/token
```
```bash
curl -X POST http://localhost:8000/token \
  -H "Content-Type: application/json" \
  -d '{"token":""}'
```
Ожидаемо: `400`, `message=VALIDATION_ERROR`.

### D) Invalid token (401 OAUTH_CODE_INVALID)
```bash
curl -X POST http://localhost:8000/token \
  -H "Content-Type: application/json" \
  -d '{"token":"<invalid_from_examples>"}'
```
Ожидаемо: `401`, `message=OAUTH_CODE_INVALID`.

### E) Expired token (401 OAUTH_CODE_INVALID)
```bash
curl -X POST http://localhost:8000/token \
  -H "Content-Type: application/json" \
  -d '{"token":"<expired_from_examples>"}'
```
Ожидаемо: `401`, `message=OAUTH_CODE_INVALID`.

### F) Internal error (DB down -> 500 INTERNAL_ERROR)
```bash
docker compose -f docker-compose.yml -f docker-compose.mock.yml stop db

curl -X POST http://localhost:8000/token \
  -H "Content-Type: application/json" \
  -d '{"token":"<valid_token>"}'

docker compose -f docker-compose.yml -f docker-compose.mock.yml start db
```
Ожидаемо: `500`, `message=INTERNAL_ERROR` при остановленной БД.

## E2E: Session S1–S6

### S1) POST /session — validation
```bash
curl -X POST http://localhost:8000/session
```
```bash
curl -X POST http://localhost:8000/session \
  -H "Content-Type: application/json" \
  -d '{"token":""}'
```
Ожидаемо: `400`, `message=VALIDATION_ERROR`.

### S2) POST /session — invalid/expired oauth token
```bash
curl -X POST http://localhost:8000/session \
  -H "Content-Type: application/json" \
  -d '{"token":"<invalid_from_examples>"}'
```
```bash
curl -X POST http://localhost:8000/session \
  -H "Content-Type: application/json" \
  -d '{"token":"<expired_from_examples>"}'
```
Ожидаемо: `401`, `message=OAUTH_CODE_INVALID`.

### S3) POST /session — success + DB verify
```bash
curl -X POST http://localhost:8000/session \
  -H "Content-Type: application/json" \
  -d '{"token":"<valid_from_examples>"}'
```
Ожидаемо: `200`, в ответе есть `session_token` и `expires_at`.

Проверка записи в БД:
```bash
docker compose -f docker-compose.yml -f docker-compose.mock.yml exec -T db \
  psql -U postgres -d postgres -c \
  "SELECT user_id, expires_at, revoked_at FROM sessions ORDER BY created_at DESC LIMIT 1;"
```
Ожидаемо: `revoked_at` = NULL, `expires_at` в будущем.

### S4) GET /session — missing/ok/expired
Без заголовка:
```bash
curl http://localhost:8000/session
```
Ожидаемо: `401`, `message=SESSION_MISSING`.

С валидным токеном:
```bash
curl http://localhost:8000/session \
  -H "Authorization: Bearer <session_token>"
```
Ожидаемо: `200`, `authenticated=true`.

С истёкшей сессией (вариант через БД):
```bash
TOKEN_HASH=$(python3 - <<'PY'
import hashlib
print(hashlib.sha256("<session_token>".encode()).hexdigest())
PY
)
docker compose -f docker-compose.yml -f docker-compose.mock.yml exec -T db \
  psql -U postgres -d postgres -c \
  "UPDATE sessions SET expires_at = now() - interval '1 minute' WHERE token_hash = '$TOKEN_HASH';"
```
Повторный `GET /session` → `401`, `message=SESSION_EXPIRED`.

### S5) POST /session/refresh — missing/expired/ok
Без заголовка:
```bash
curl -X POST http://localhost:8000/session/refresh
```
Ожидаемо: `401`, `message=SESSION_MISSING`.

С истёкшей/отозванной:
```bash
curl -X POST http://localhost:8000/session/refresh \
  -H "Authorization: Bearer <session_token>"
```
Ожидаемо: `401`, `message=SESSION_EXPIRED`.

С валидной:
```bash
curl -X POST http://localhost:8000/session/refresh \
  -H "Authorization: Bearer <session_token>"
```
Ожидаемо: `200`, `expires_at` увеличился (проверить в БД).

### S6) DELETE /session — logout
Без заголовка:
```bash
curl -X DELETE http://localhost:8000/session
```
Ожидаемо: `401`, `message=SESSION_MISSING`.

С валидной сессией:
```bash
curl -X DELETE http://localhost:8000/session \
  -H "Authorization: Bearer <session_token>"
```
Ожидаемо: `200`, `authenticated=false`.

Проверка в БД:
```bash
docker compose -f docker-compose.yml -f docker-compose.mock.yml exec -T db \
  psql -U postgres -d postgres -c \
  "SELECT revoked_at FROM sessions WHERE token_hash = '<token_hash>';"
```
Ожидаемо: `revoked_at` заполнен.

После logout:
```bash
curl http://localhost:8000/session \
  -H "Authorization: Bearer <session_token>"
```
Ожидаемо: `401`, `message=SESSION_EXPIRED`.

## Contract checks
- Формат ошибки всегда: `{status,message,timestamp}`.
- Коды ошибок:
  - `400`: `VALIDATION_ERROR`
  - `401`: `SESSION_MISSING` / `SESSION_EXPIRED` / `OAUTH_CODE_INVALID`
  - `500`: `INTERNAL_ERROR`
- OpenAPI:
```bash
curl -s http://localhost:8000/openapi.json | head -n 5
```
Проверить наличие `ErrorCode` enum в `components.schemas`.

## Security checks
- В логах API нет raw oauth/session токенов:
```bash
docker compose -f docker-compose.yml -f docker-compose.mock.yml logs --tail=200 api
```
- Mock issuer не поднимается без `docker-compose.mock.yml`:
```bash
docker compose -f docker-compose.yml ps
```
Ожидаемо: только `api` и `db`.
- `.env.example` не содержит секретов.

## Troubleshooting
- API не стартует из-за БД:
  - `docker compose ... ps` (DB должна быть `healthy`);
  - `docker compose ... logs db` и `docker compose ... logs api`;
  - перезапустить `docker compose ... restart api` после готовности БД.

## Result
PASS (Token A–F и Session S1–S6 пройдены в Docker).
