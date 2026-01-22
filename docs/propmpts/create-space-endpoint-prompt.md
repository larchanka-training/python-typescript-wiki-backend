# Инструкция для реализации эндпойнта создания пространства (Space)

Реализуй функционал создания нового пространства (Space) согласно спецификации в [api/docs/spaces-api-endpoints-and-logic.md](docs/spaces-api-endpoints-and-logic.md).

## Технический стек и контекст
- **Framework**: FastAPI (async).
- **Database**: PostgreSQL. Используется `asyncpg` для SQL-запросов и SQLAlchemy для определения моделей (необходимы для миграций Alembic).
- **Архитектура**: API Routes -> Services -> Repositories.
- **Auth**: Сессионная. Доступ к `user_id` можно получить через `SessionService` (см. `api/app/api/v1/routes/session.py`).
- **Ошибки**: Используй `AppError` и `ErrorCode` из `app.core.errors`. Все ошибки должны возвращаться в формате `{status, message, timestamp}`.

## Шаги реализации

### 1. Модели базы данных (`api/app/models.py`)
Добавь новые модели (SQLAlchemy):
- **Space**: поля `id` (UUID, primary key), `name` (String(255), non-unique), `deleted_at` (DateTime, timezone=True), `delete_scheduled_at` (DateTime, timezone=True).
- **SpaceMembership**: таблица связей пользователей и пространств. Поля: `user_id` (int, ForeignKey users.id), `space_id` (UUID, ForeignKey spaces.id), `role` (String(64), возможные значения: `owner`, `admin`, `editor`, `viewer`).

### 2. Миграции базы данных
После добавления моделей в `models.py`, создай и примени миграцию:
- Выполни команду: `alembic revision --autogenerate -m "create spaces and space_memberships tables"`.
- Проверь содержимое созданного файла в `api/alembic/versions/`.
- Примени миграцию: `alembic upgrade head`.
- Обрати внимание: команды нужно запускать из директории `api`, где находится `alembic.ini`.

### 3. Репозиторий (`api/app/repositories/spaces.py`)
Создай `SpaceRepository`, работающий через `asyncpg`:
- Метод `create_space(name: str, owner_id: int) -> UUID`:
  - Должен выполняться в транзакции.
  - Сначала вставляет запись в таблицу `spaces` и получает `id`.
  - Затем вставляет запись в `space_memberships` с этим `id`, `owner_id` и ролью `owner`.
  - Возвращает UUID созданного пространства.

### 4. Сервисный слой
- В `api/app/services/models.py` добавь DTO (dataclasses) если требуется (например, `SpaceID`).
- Создай `api/app/services/space_service.py` с классом `SpaceService`:
  - Метод `create_space(name: str, user_id: int) -> UUID`.
  - Метод должен вызывать репозиторий.

### 5. Схемы Pydantic (`api/app/api/v1/schemas/spaces.py`)
Создай схемы для запроса и ответа:
- `SpaceCreateRequest`: `{ "name": str }`
- `SpaceCreateResponse`: `{ "id": UUID }`.

### 6. API Маршруты (`api/app/api/v1/routes/spaces.py`)
- Создай роутер для `/spaces`.
- Реализуй эндпойнт `POST /spaces`:
  - Требует авторизации (Bearer token).
  - Валидирует, что `name` не пустой (возвращает `400 VALIDATION_ERROR` при ошибке).
  - Вызывает `SpaceService`.
  - Возвращает `201 Created` и ID пространства.
  - Обязательно добавь описание ответов (201, 400, 401, 500) с использованием примеров из `ErrorCode`.

### 7. Регистрация и зависимости
- В `api/app/api/deps.py` добавь функции `get_space_repository` и `get_space_service`.
- В `api/app/main.py` подключи новый роутер: `app.include_router(spaces_router)`.

## Важные детали
- Соблюдай стиль именования и структуру существующих файлов (например, `UserRepository`).
- Не забудь импорты `from __future__ import annotations` и использование `Annotated` для `Depends`.
- Убедись, что все эндпойнты возвращают `AppError` в случае бизнес-ошибок или проблем с валидацией, чтобы избежать стандартных 422 ответов FastAPI.

При реализации ориентируйся на `api/app/api/v1/routes/session.py` и `api/app/repositories/users.py` как на эталонные примеры.
