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
  - `OAUTH_MOCK_FIXED_CREATED_AT` (опционально, для детерминированных токенов mock)

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
Ожидаемо: ключи `valid`, `expired`, `invalid`, `invalid_hmac`, `invalid_base64`, `missing_fields`, `wrong_types`.
Если задан `OAUTH_MOCK_FIXED_CREATED_AT`, токены (кроме `invalid`/`invalid_base64`) будут стабильны между запусками.

#### A1) Быстрое извлечение токенов (без jq)
```bash
TOKENS_JSON=$(curl -s http://localhost:9001/oauth/token/examples)
VALID=$(python3 - <<'PY'
import json, os
print(json.loads(os.environ["TOKENS_JSON"])["valid"])
PY
)
EXPIRED=$(python3 - <<'PY'
import json, os
print(json.loads(os.environ["TOKENS_JSON"])["expired"])
PY
)
INVALID=$(python3 - <<'PY'
import json, os
print(json.loads(os.environ["TOKENS_JSON"])["invalid"])
PY
)
INVALID_HMAC=$(python3 - <<'PY'
import json, os
print(json.loads(os.environ["TOKENS_JSON"])["invalid_hmac"])
PY
)
INVALID_BASE64=$(python3 - <<'PY'
import json, os
print(json.loads(os.environ["TOKENS_JSON"])["invalid_base64"])
PY
)
MISSING_FIELDS=$(python3 - <<'PY'
import json, os
print(json.loads(os.environ["TOKENS_JSON"])["missing_fields"])
PY
)
WRONG_TYPES=$(python3 - <<'PY'
import json, os
print(json.loads(os.environ["TOKENS_JSON"])["wrong_types"])
PY
)
```

#### A2) Проверка детерминированности (опционально)
> Используйте, если нужно убедиться, что при `OAUTH_MOCK_FIXED_CREATED_AT` токены стабильны между запусками.

1) Остановить mock и перезапустить с фиксированным created_at:
```bash
docker compose -f docker-compose.yml -f docker-compose.mock.yml down
export OAUTH_MOCK_FIXED_CREATED_AT=1700000000
docker compose -f docker-compose.yml -f docker-compose.mock.yml up --build -d
```
2) Считать токены (run #1):
```bash
curl -s http://localhost:9001/oauth/token/examples > /tmp/tokens_run1.json
```
3) Перезапустить mock и повторить (run #2):
```bash
docker compose -f docker-compose.yml -f docker-compose.mock.yml restart mock_oauth
curl -s http://localhost:9001/oauth/token/examples > /tmp/tokens_run2.json
```
4) Сравнить (ожидается совпадение значений `valid/expired/invalid_hmac/missing_fields/wrong_types`):
```bash
python3 - <<'PY'
import json
keys = ["valid","expired","invalid_hmac","missing_fields","wrong_types"]
with open("/tmp/tokens_run1.json") as f1, open("/tmp/tokens_run2.json") as f2:
    a = json.load(f1)
    b = json.load(f2)
print({k: a[k]==b[k] for k in keys})
PY
```

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

Дополнительно (edge-cases из mock):
- `invalid_hmac` — base64 валиден, но HMAC подпорчен → `401`
- `invalid_base64` — base64 decode падает → `401`
- `missing_fields` — payload без обязательных полей → `401`
- `wrong_types` — типы полей некорректные → `401`

Пример (используйте значения из A1):
```bash
curl -X POST http://localhost:8000/token \
  -H "Content-Type: application/json" \
  -d "{\"token\":\"$INVALID_HMAC\"}"
```
```bash
curl -X POST http://localhost:8000/token \
  -H "Content-Type: application/json" \
  -d "{\"token\":\"$INVALID_BASE64\"}"
```
```bash
curl -X POST http://localhost:8000/token \
  -H "Content-Type: application/json" \
  -d "{\"token\":\"$MISSING_FIELDS\"}"
```
```bash
curl -X POST http://localhost:8000/token \
  -H "Content-Type: application/json" \
  -d "{\"token\":\"$WRONG_TYPES\"}"
```

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
