# Spaces API — Реализованные эндпойнты

## Обзор

Этот документ описывает **реализованные** API эндпойнты для работы с пространствами (Spaces), включая создание, получение, мягкое удаление и восстановление.

Все эндпойнты:
- Требуют **авторизацию** через Bearer Token в заголовке `Authorization: Bearer <session_token>`
- Используют базовый путь `/api/v1`
- Возвращают единый формат ошибок: `{status: "error", message: "ERROR_CODE", timestamp: "ISO_8601"}`

---

## Таблица эндпойнтов

| Метод | Путь | Описание | Статус |
|---|---|---|---|
| POST | `/api/v1/spaces` | Создать пространство | 201 Created |
| GET | `/api/v1/spaces/{space_id}` | Получить пространство | 200 OK |
| DELETE | `/api/v1/spaces/{space_id}` | Мягко удалить пространство | 204 No Content |
| PATCH | `/api/v1/spaces/{space_id}/restore` | Восстановить удалённое пространство | 200 OK |

---

## POST /api/v1/spaces — Создание пространства

### Описание
Создает новое пространство. Создатель автоматически становится владельцем (`owner`) пространства.

### Авторизация
✓ Требуется активная сессия

### Request Body
```json
{
  "name": "My Awesome Space"
}
```

### Валидация
- `name` — **обязательно**, строка, 1-255 символов
- Допускаются дублирующиеся имена

### Success Response (201 Created)
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Error Responses

| Случай | HTTP | Message |
|---|---|---|
| Пустое/невалидное имя | 400 | VALIDATION_ERROR |
| Нет сессии | 401 | SESSION_MISSING |
| Сессия истекла | 401 | SESSION_EXPIRED |
| Ошибка БД | 500 | INTERNAL_ERROR |

### Example
```bash
curl -X POST http://localhost:8000/api/v1/spaces \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Team Documentation"}'
```

---

## GET /api/v1/spaces/{space_id} — Получение пространства

### Описание
Получает информацию о конкретном пространстве с учётом прав доступа и статуса удаления.

### Авторизация
✓ Требуется активная сессия

### URL Parameters
- `space_id` — UUID пространства

### Visibility Rules (критично)

#### Активное пространство (deleted = false)
- **Видят**: все авторизованные пользователи

#### Удалённое пространство, в окне ≤ 7 дней (deleted = true, now < delete_scheduled_at)
- **Видят**: владелец (owner) пространства и суперадмин
- **Ответ включает**: `deleted_at`, `delete_scheduled_at` для владельца

#### Удалённое пространство, после 7 дней (now >= delete_scheduled_at)
- **Видят**: только суперадмин (`permission == "admin"`)
- **Остальные**: получают 404

### Success Response — Активное пространство (200 OK)
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Team Documentation",
  "deleted": false,
  "deleted_at": null,
  "delete_scheduled_at": null
}
```

### Success Response — Удалённое пространство (200 OK)
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Old Project",
  "deleted": true,
  "deleted_at": "2026-02-18T12:00:00Z",
  "delete_scheduled_at": "2026-02-25T12:00:00Z"
}
```

### Error Responses

| Случай | HTTP | Message |
|---|---|---|
| Пространство не найдено | 404 | VALIDATION_ERROR |
| Удалено > 7 дней и вы не админ | 403 | VALIDATION_ERROR |
| Нет сессии | 401 | SESSION_MISSING |
| Сессия истекла | 401 | SESSION_EXPIRED |
| Ошибка БД | 500 | INTERNAL_ERROR |

### Response Fields
- `id` — UUID пространства
- `name` — название пространства
- `deleted` — флаг: true если пространство помечено как удалённое
- `deleted_at` — время удаления (ISO 8601, null если активно)
- `delete_scheduled_at` — время, когда пространство скроется для non-admin (ISO 8601)

### Example
```bash
curl -X GET http://localhost:8000/api/v1/spaces/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN"
```

---

## DELETE /api/v1/spaces/{space_id} — Мягкое удаление

### Описание
Помечает пространство как удалённое (soft delete). Пространство **не удаляется из БД**, но становится скрытым. Владелец может восстановить его в течение 7 дней.

### Авторизация
✓ Требуется активная сессия

### Права доступа
**Только**:
- Владелец пространства (`owner`)
- Суперадмин (`permission == "admin"`)

### Логика

При успехе выполняются действия:

1. `deleted_at = now()` — фиксирует момент удаления
2. `delete_scheduled_at = now() + 7 days` — устанавливает момент, когда пространство скроется для владельца
3. Пространство становится **невидимым** для обычных пользователей
4. Владелец **может видеть** пространство (как "удалённое") в течение 7 дней для восстановления
5. После 7 дней пространство видно только суперадмину

### URL Parameters
- `space_id` — UUID пространства

### Success Response (204 No Content)
Без тела. Только заголовок статуса.

### Error Responses

| Случай | HTTP | Message |
|---|---|---|
| Пространство не найдено | 404 | VALIDATION_ERROR |
| Нет прав (не owner и не admin) | 403 | VALIDATION_ERROR |
| Нет сессии | 401 | SESSION_MISSING |
| Сессия истекла | 401 | SESSION_EXPIRED |
| Ошибка БД | 500 | INTERNAL_ERROR |

### Example
```bash
curl -X DELETE http://localhost:8000/api/v1/spaces/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN"
```

---

## PATCH /api/v1/spaces/{space_id}/restore — Восстановление

### Описание
Восстанавливает удалённое пространство, сбрасывая флаги soft delete. Пространство становится видимым для всех авторизованных пользователей.

### Авторизация
✓ Требуется активная сессия

### Права доступа

#### Суперадмин (permission == "admin")
- **Может восстановить**: любое пространство в любой момент (даже если прошло > 7 дней)

#### Владелец (owner)
- **Может восстановить**: только если пространство удалено и текущее время < `delete_scheduled_at` (в окне ≤ 7 дней)
- **Не может восстановить**: если прошло > 7 дней после удаления

### Логика

При успехе выполняются действия:

1. `deleted_at = NULL` — сбрасывает флаг удаления
2. `delete_scheduled_at = NULL` — удаляет расписание скрытия
3. Пространство становится **активным** и видно всем авторизованным пользователям

### URL Parameters
- `space_id` — UUID пространства

### Success Response (200 OK)
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Old Project",
  "deleted": false,
  "deleted_at": null,
  "delete_scheduled_at": null
}
```

### Error Responses

| Случай | HTTP | Message |
|---|---|---|
| Пространство не найдено | 404 | VALIDATION_ERROR |
| Пространство не удалено (уже активно) | 404 | VALIDATION_ERROR |
| Нет прав / owner вне окна 7 дней | 403 | VALIDATION_ERROR |
| Нет сессии | 401 | SESSION_MISSING |
| Сессия истекла | 401 | SESSION_EXPIRED |
| Ошибка БД | 500 | INTERNAL_ERROR |

### Example
```bash
curl -X PATCH http://localhost:8000/api/v1/spaces/550e8400-e29b-41d4-a716-446655440000/restore \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN" \
  -H "Content-Type: application/json"
```

---

## Мягкое удаление (Soft Delete) — Поведение

### Временная шкала

```
Время создания        Время удаления         delete_scheduled_at   Действие
[T0]                  [T0 + 0 sec]           [T0 + 7 days]         ← Окно восстановления (7 дней)
|                     |                      |
Пространство активно  Marked deleted_at      Owner может видеть     Owner теряет видимость
Видно: все            Видно: owner + admin   Может восстановить     Admin видит; Owner не видит
                      Может восстановить     Можно восстановить
```

### Таблица видимости

| Статус | Owner видит | Non-owner видит | Admin видит |
|---|---|---|---|
| Активно (deleted_at = NULL) | ✓ | ✓ | ✓ |
| Удалено (0 < время < 7 дней) | ✓ (marked) | ✗ | ✓ (marked) |
| Удалено (время ≥ 7 дней) | ✗ | ✗ | ✓ (marked) |

### Данные БД

Таблица `spaces`:

| Колонка | Тип | Описание |
|---|---|---|
| `id` | UUID | Первичный ключ |
| `name` | VARCHAR(255) | Название пространства |
| `deleted_at` | TIMESTAMP WITH TZ / NULL | Момент soft delete (NULL = активно) |
| `delete_scheduled_at` | TIMESTAMP WITH TZ / NULL | Когда пространство скроется (NULL = активно или уже скрыто) |

---

## Тестовые сценарии

### Сценарий 1: Создание и получение пространства
```
1. POST /api/v1/spaces {"name": "Test"} → 201 {id: "ABC123"}
2. GET /api/v1/spaces/ABC123 → 200 {id, name, deleted: false, ...}
✓ Pass
```

### Сценарий 2: Удаление и восстановление (в окне 7 дней)
```
1. DELETE /api/v1/spaces/ABC123 (as owner) → 204
2. GET /api/v1/spaces/ABC123 (as owner) → 200 {deleted: true, deleted_at: "...", ...}
3. PATCH /api/v1/spaces/ABC123/restore (as owner) → 200 {deleted: false}
✓ Pass
```

### Сценарий 3: Удаление + попытка восстановления вне окна (owner)
```
1. DELETE /api/v1/spaces/ABC123 (as owner) → 204
2. [Ждём 7+ дней]
3. GET /api/v1/spaces/ABC123 (as owner) → 403 или 404
4. PATCH /api/v1/spaces/ABC123/restore (as owner) → 403
✓ Pass
```

### Сценарий 4: Удаление + восстановление (superadmin вне окна)
```
1. DELETE /api/v1/spaces/ABC123 (as owner) → 204
2. [Ждём 7+ дней]
3. PATCH /api/v1/spaces/ABC123/restore (as superadmin) → 200
✓ Pass (admin может восстановить в любой момент)
```

### Сценарий 5: Non-owner не может удалить
```
1. DELETE /api/v1/spaces/ABC123 (as random_user) → 403
✓ Pass
```

---

## Коды ошибок

Все ошибки используют **единый формат**:

```json
{
  "status": "error",
  "message": "ERROR_CODE",
  "timestamp": "2026-02-18T15:30:45Z"
}
```

### Используемые коды

| Код | HTTP | Значение |
|---|---|---|
| VALIDATION_ERROR | 400, 403, 404 | Валидация не пройдена, доступ запрещён, ресурс не найден |
| SESSION_MISSING | 401 | Bearer token не передан или пуст |
| SESSION_EXPIRED | 401 | Сессия истекла или отозвана |
| INTERNAL_ERROR | 500 | Ошибка сервера |

---

## Миграция БД

Для добавления колонок `deleted_at` и `delete_scheduled_at` используется миграция Alembic:

**Файл**: `alembic/versions/0006_add_deleted_fields.py`

Миграция идемпотентна и использует `ADD COLUMN IF NOT EXISTS`, поэтому безопасна для DBs, которые уже имеют эти колонки.

```bash
# Применить миграции
alembic upgrade head

# Откатить последнюю миграцию
alembic downgrade -1
```

---

## Примеры использования

### Создать пространство
```bash
curl -X POST http://localhost:8000/api/v1/spaces \
  -H "Authorization: Bearer abc123token" \
  -H "Content-Type: application/json" \
  -d '{"name": "Engineering Docs"}'

# Ответ:
# {
#   "id": "550e8400-e29b-41d4-a716-446655440000"
# }
```

### Получить пространство
```bash
curl -X GET http://localhost:8000/api/v1/spaces/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer abc123token"

# Ответ (активное):
# {
#   "id": "550e8400-e29b-41d4-a716-446655440000",
#   "name": "Engineering Docs",
#   "deleted": false,
#   "deleted_at": null,
#   "delete_scheduled_at": null
# }
```

### Удалить пространство
```bash
curl -X DELETE http://localhost:8000/api/v1/spaces/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer abc123token"

# Ответ: 204 No Content (пусто)
```

### Восстановить пространство
```bash
curl -X PATCH http://localhost:8000/api/v1/spaces/550e8400-e29b-41d4-a716-446655440000/restore \
  -H "Authorization: Bearer abc123token" \
  -H "Content-Type: application/json"

# Ответ:
# {
#   "id": "550e8400-e29b-41d4-a716-446655440000",
#   "name": "Engineering Docs",
#   "deleted": false,
#   "deleted_at": null,
#   "delete_scheduled_at": null
# }
```

---

## Отличия от планового документа

Реализованные эндпойнты отличаются от `spaces-api-endpoints-and-logic.md` в следующих моментах:

| Аспект | План | Реализация |
|---|---|---|
| GET /spaces (список) | Планировался | **Не реализован** (в TODO) |
| GET /spaces/{id} | Планировался | ✓ Реализован |
| POST /spaces | ✓ Планировался | ✓ Реализован |
| DELETE /spaces/{id} | ✓ Планировался | ✓ Реализован (204 вместо 200) |
| PATCH /spaces/{id}/restore | POST планировался | ✓ Реализован как PATCH |
| Коды ошибок | SPACE_NOT_FOUND, FORBIDDEN | VALIDATION_ERROR (объединены) |

---

## Future Work / TODO

- [ ] Добавить `GET /api/v1/spaces` для получения списка всех пространств пользователя
- [ ] Добавить explicit ErrorCode (`SPACE_NOT_FOUND`, `SPACE_FORBIDDEN`) вместо VALIDATION_ERROR
- [ ] Интеграционные тесты для soft-delete сценариев (7-дневное окно)
- [ ] Hard-delete спустя 7 дней (scheduled job)
- [ ] Поддержка `GET /api/v1/spaces?include_deleted=true` для админов
