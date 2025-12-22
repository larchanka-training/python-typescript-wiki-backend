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

### Запуск тестов
```bash
pytest or you can use `pytest --verbose` for more information about tests
```