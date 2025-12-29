## Backend

FastAPI backend с подключением к PostgreSQL через `asyncpg`.

### Configuration

Переменные окружения:

- `DATABASE_URL` (пример в `.env.example`)
- `OAUTH_NAME_APPLICATION_ID`
- `OAUTH_NAME_SECRET_KEY`
- `TOKEN_TTL_SECONDS`
- `SESSION_TTL_SECONDS`

См. также: `docs/Формат ошибок.md` (source of truth), `docs/errors.md` (краткая выжимка для фронта).
Подробно про эндпойнт `/token`: `docs/token-endpoint.md`.
Эндпойнты `/session*`: `docs/session-endpoints.md`.
E2E проверка в Docker: `docs/token-e2e-docker-test.md`.

### Auth: Token

Endpoint:
- `POST /token`

Передача токена:
- `{"token": "..."}` в теле запроса (JSON)

Примеры:

```bash
curl -X POST http://localhost:8000/token \
  -H "Content-Type: application/json" \
  -d '{"token":"<token>"}'
```

#### Responses

Success:
- `200 OK` — пользователь создан или обновлён

Пример ответа:

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

Errors (единый формат):

```json
{
  "status": "error",
  "message": "OAUTH_CODE_INVALID",
  "timestamp": "2025-01-01T12:00:00Z"
}
```

| HTTP | message | Когда |
| --- | --- | --- |
| 400 | VALIDATION_ERROR | Нет token/пустая строка/неверный формат |
| 401 | OAUTH_CODE_INVALID | Токен невалиден или просрочен |
| 500 | INTERNAL_ERROR | Ошибка БД/непредвиденная ошибка |

#### Error Codes

Фактические enum-коды из реализации:
- `VALIDATION_ERROR`
- `OAUTH_CODE_INVALID`
- `SESSION_MISSING`
- `SESSION_EXPIRED`
- `INTERNAL_ERROR`

### Auth: Session

Эндпойнты:
- `POST /session` — создать сессию по oauth.name токену
- `GET /session` — проверить текущую сессию
- `POST /session/refresh` — продлить срок жизни
- `DELETE /session` — logout (отзыв сессии)

Передача session token:
- `Authorization: Bearer <session_token>`

Создание сессии:

```bash
curl -X POST http://localhost:8000/session \
  -H "Content-Type: application/json" \
  -d '{"token":"<oauth_token>"}'
```

Пример ответа:

```json
{
  "authenticated": true,
  "session_token": "opaque-session-token",
  "expires_at": "2024-01-01T12:00:00Z",
  "user": {
    "telegram_id": 123456,
    "username": "user",
    "created_at": "2024-01-01T12:00:00Z",
    "last_login_at": "2024-01-01T12:00:00Z"
  }
}
```

### Database

Таблица `users` (ключевые поля):
- `id` (pk)
- `telegram_id` (unique) — стабильный идентификатор
- `username` (nullable)
- `first_name` / `last_name` / `photo_url` (nullable)
- `permission` (nullable)
- `created_at`, `updated_at`, `last_login_at`

### Миграции (Alembic)

Применить миграции:

```bash
alembic upgrade head
```

Создать новую миграцию (autogenerate):

```bash
alembic revision --autogenerate -m "message"
```

### Local Run

1) Установить зависимости:

```bash
pip install -r requirements.txt
```

2) Поднять PostgreSQL (пример через docker):

```bash
docker run --rm -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:16
```

3) Запустить приложение:

```bash
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/postgres"
export OAUTH_NAME_APPLICATION_ID="local-app"
export OAUTH_NAME_SECRET_KEY="local-secret"
export TOKEN_TTL_SECONDS=86400
fastapi dev app/main.py --host 0.0.0.0 --port 8000
```

Проверка подключения к БД: `GET /health/db`
OpenAPI: `GET /docs`

### Local OAuth mock (Docker)

Для локального тестирования без реального oauth.name используйте mock-сервис (issuer).
Он запускается отдельным compose-файлом и не влияет на обычный запуск API.

Запуск:

```bash
docker compose -f docker-compose.yml -f docker-compose.mock.yml up --build
```

Mock слушает:
- `http://localhost:9001/oauth/token/issue` — выдать токен по payload
- `http://localhost:9001/oauth/token/examples` — готовые кейсы:
  - `valid`, `expired`, `invalid`
  - `invalid_hmac`, `invalid_base64`
  - `missing_fields`, `wrong_types`

Mock использует те же `OAUTH_NAME_APPLICATION_ID`, `OAUTH_NAME_SECRET_KEY`, `TOKEN_TTL_SECONDS`.
Для детерминированных токенов можно задать `OAUTH_MOCK_FIXED_CREATED_AT` (unix timestamp).

Примеры:

```bash
curl http://localhost:9001/oauth/token/examples
```

```bash
curl -X POST http://localhost:9001/oauth/token/issue \
  -H "Content-Type: application/json" \
  -d '{"telegram_id":123456,"username":"demo"}'
```

```bash
curl -X POST http://localhost:8000/token \
  -H "Content-Type: application/json" \
  -d '{"token":"<valid_token>"}'
```

### Testing

Запуск тестов:

```bash
pytest -q
pytest --verbose
```

Покрытые кейсы:
- missing/empty token -> 400
- invalid/expired token -> 401
- internal error -> 500
- valid token + new user -> 200 (created=true)
- valid token + existing user -> 200 (created=false)
- session create/check/refresh/logout -> 200/401

### Frontend Integration Notes

- `message` — машинный код; фронт сам маппит его на локализованные тексты.
- OpenAPI описывает `message` как enum, чтобы `openapi-typescript` генерировал типы.

### Docker Compose

```bash
docker compose up --build
```

При старте контейнера `api` автоматически выполняется `alembic upgrade head`, после чего таблица `tmp` появится в БД (видна в pgAdmin).
# Python TypeScript Wiki Backend

FastAPI backend приложение.

## 🛠️ Технологии

- **FastAPI** - современный веб-фреймворк для Python
- **Ruff** - быстрый линтер и форматтер для Python
- **Pre-commit** - инструмент для автоматической проверки кода перед коммитом

## 📦 Установка зависимостей

### 1. Создайте виртуальное окружение (рекомендуется)

```bash
 python -m venv .venv
 # On Windows:
 .venv\Scripts\activate
 # On Unix/MacOS:
 source .venv/bin/activate
```

### 2. Установите все зависимости

```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## 🔧 Настройка Pre-commit Hooks

В проекте настроены pre-commit hooks, которые автоматически проверяют код перед каждым коммитом.

### Установка hooks

После установки зависимостей выполните:

```bash
pre-commit install
```

Это установит git hooks, которые будут автоматически запускаться при каждом `git commit`.

### Что проверяют hooks

При каждом коммите автоматически запускаются:

1. **Стандартные проверки:**
   - `check-merge-conflict` - проверка конфликтов слияния
   - `trailing-whitespace` - удаление пробелов в конце строк
   - `end-of-file-fixer` - добавление переноса строки в конце файлов
   - `check-yaml` - проверка синтаксиса YAML файлов
   - `check-toml` - проверка синтаксиса TOML файлов
   - `check-json` - проверка синтаксиса JSON файлов

2. **Ruff проверки:**
   - `ruff-check` - проверка кода на соответствие правилам (linting) с автоматическим исправлением
   - `ruff-format` - форматирование кода

### Важно

Если код не соответствует правилам ruff, коммит будет **заблокирован**. Нужно исправить ошибки перед повторной попыткой коммита.

## 🚀 Использование Ruff

### Ручная проверка кода

```bash
# Проверка всего проекта
ruff check .

# Проверка конкретного файла
ruff check app/main.py

# Проверка с автоматическим исправлением
ruff check . --fix
```

### Форматирование кода

```bash
# Форматирование всего проекта
ruff format .

# Проверка форматирования (без изменений)
ruff format --check .
```

### Подробный вывод

```bash
# Полный вывод с деталями
ruff check . --output-format=full

# Статистика по правилам
ruff check . --statistics
```

## ✅ Проверка работы Pre-commit Hooks

### Проверка всех hooks

```bash
pre-commit run --all-files
```

Эта команда запустит все hooks для всех файлов в проекте, как при коммите.

### Проверка конкретного hook

```bash
# Только ruff проверка
pre-commit run ruff-check --all-files

# Только ruff форматирование
pre-commit run ruff-format --all-files

# Только проверка YAML
pre-commit run check-yaml --all-files
```

### Проверка для конкретных файлов

```bash
pre-commit run ruff-check --files app/main.py
```

## 📝 Конфигурация Ruff

Настройки ruff находятся в файле `pyproject.toml`. Там настроены:

- Длина строки: 120 символов
- Включены все правила (`extend-select = ["ALL"]`)
- Игнорируются некоторые правила (docstrings, TODO комментарии и т.д.)
- Настройки форматирования и сортировки импортов

Подробнее о настройках см. в `pyproject.toml`.

## 🔄 Обновление Pre-commit Hooks

Для обновления версий hooks до последних:

```bash
pre-commit autoupdate
```

## 🐛 Решение проблем

### Hooks не запускаются при коммите

1. Проверьте, что hooks установлены:
   ```bash
   pre-commit install
   ```

2. Проверьте, что файл `.pre-commit-config.yaml` существует

3. Проверьте работу hooks вручную:
   ```bash
   pre-commit run --all-files
   ```

### Ruff находит ошибки, которые нужно исправить

1. Запустите ruff с автоисправлением:
   ```bash
   ruff check . --fix
   ```

2. Или исправьте ошибки вручную согласно выводу ruff

3. После исправления повторите коммит

### Обход hooks (не рекомендуется)

Если нужно временно обойти проверки (например, для экстренного коммита):

```bash
git commit --no-verify -m "your message"
```
