## Backend

FastAPI backend с подключением к PostgreSQL через `asyncpg`.

### Настройка

Переменные окружения:

- `DATABASE_URL` (пример в `.env.example`)

### Миграции (Alembic)

Применить миграции:

```bash
alembic upgrade head
```

Создать новую миграцию (autogenerate):

```bash
alembic revision --autogenerate -m "message"
```

### Локальный запуск

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
fastapi dev app/main.py --host 0.0.0.0 --port 8000
```

Проверка подключения к БД: `GET /health/db`

### Docker Compose

```bash
docker compose up --build
```

При старте контейнера `api` автоматически выполняется `alembic upgrade head`, после чего таблица `tmp` появится в БД (видна в pgAdmin).
