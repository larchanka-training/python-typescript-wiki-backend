# Session Endpoints

## Кратко
Сессии stateful и хранятся в БД. Клиент получает `session_token` из `POST /session`
и передаёт его в заголовке `Authorization: Bearer <session_token>` для всех `/session*`.

## Контракт

### POST /session
Создать сессию по oauth.name токену.

Request:
```json
{ "token": "<oauth_token>" }
```

Response 200:
```json
{
  "authenticated": true,
  "session_token": "<session_token>",
  "expires_at": "2024-01-01T12:00:00Z",
  "user": {
    "telegram_id": 123456,
    "username": "user",
    "created_at": "2024-01-01T12:00:00Z",
    "last_login_at": "2024-01-01T12:00:00Z"
  }
}
```
Примечание: если в системе ещё нет superuser, текущий пользователь будет назначен `users.is_superuser = true`.

### GET /session
Проверка сессии.

Header:
`Authorization: Bearer <session_token>`

Response 200:
```json
{
  "authenticated": true,
  "expires_at": "2024-01-01T12:00:00Z",
  "user": { "...": "..." }
}
```

### POST /session/refresh
Продление срока жизни сессии.

Header:
`Authorization: Bearer <session_token>`

Response 200:
```json
{
  "authenticated": true,
  "expires_at": "2024-01-01T12:00:00Z",
  "user": { "...": "..." }
}
```

### DELETE /session
Logout (отзыв сессии).

Header:
`Authorization: Bearer <session_token>`

Response 200:
```json
{ "authenticated": false }
```

## Ошибки
Единый формат: `{status,message,timestamp}`.

| Сценарий | HTTP | message |
| --- | --- | --- |
| Некорректный запрос/заголовок | 400 | VALIDATION_ERROR |
| Сессия отсутствует | 401 | SESSION_MISSING |
| Сессия истекла/отозвана | 401 | SESSION_EXPIRED |
| Невалидный oauth токен | 401 | OAUTH_CODE_INVALID |
| Ошибка сервера/БД | 500 | INTERNAL_ERROR |

## Конфигурация
- `SESSION_TTL_SECONDS` — срок жизни сессии в секундах.
