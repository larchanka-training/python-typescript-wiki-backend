Документ описывает целевую схему деплоя проекта на Render.com и взаимодействие с GitHub Actions: окружения (dev/acc/prd), переменные окружения, секреты, миграции, а также правила, которые не дают “случайно уронить прод”.

Основано на проектной документации и артефактах репозитория:
- Контракт `/token` и обязательные env-переменные (включая mock-only переменные) — `docs/token-endpoint.md`
- Контракт `/session*` и зависимость от `SESSION_TTL_SECONDS` — `docs/session-endpoints.md`
- Единый формат ошибок `{status,message,timestamp}` и политика кодов (без 422) — `docs/Формат ошибок.md`
- Логика Spaces `/spaces*` (требует активную сессию; soft-delete и окно восстановления) — `docs/spaces-api-endpoints-and-logic.md`
- Миграции Alembic — `docs/Миграции.md`
- E2E проверка токена/сессий в Docker — `docs/token-e2e-docker-test.md`
- Структура репозитория — `docs/project-structure.md`

---

## 1) Цель и границы

Цель: настроить воспроизводимый и безопасный деплой на Render.com с раздельными окружениями и понятной “владельческой моделью” переменных:
- runtime-секреты и конфиг приложения — в Render (Env Groups / Service Env),
- CI/CD секреты — в GitHub Secrets,
- production деплой — только через ручной гейт (GitHub Environments required reviewers),
- миграции БД — контролируемо (без гонок и без “две миграции одновременно”).

---

## 2) Что уже есть в репозитории (важные факты)

В монорепозитории присутствует `render.yaml` (IaC для Render):
- EnvVarGroup `wiki-secrets` с `OAUTH_NAME_APPLICATION_ID`, `OAUTH_NAME_SECRET_KEY` (оба `sync: false` — секреты не синкаются автоматически).
- Managed Postgres `wiki-db` (region: frankfurt, plan: free).
- Сервис API `wiki-api` (python, rootDir: `api`), env vars:
  - `DATABASE_URL` из базы,
  - `TOKEN_TTL_SECONDS=86400`,
  - `SESSION_TTL_SECONDS=604800`,
  - + секреты из `wiki-secrets`.
- Сервис фронта `wiki-frontend` (node, rootDir: `frontend`), env vars:
  - `VITE_API_URL` задан значением публичного URL API.

Также `render.yaml` содержит buildCommand, который тянет git submodules через `GITHUB_USERNAME`/`GITHUB_ACCESS_TOKEN` — эти значения должны быть доступны на Render как секретные env vars.

Отдельно: в монорепозитории есть GitHub workflow `deploy.yml`, но он деплоит через SSH и docker-compose на внешний хост (не Render). Мы фиксируем целевую схему деплоя на Render и (опционально) добавляем workflow, который дергает Render deploy hooks.

---

## 3) “Одна схема” архитектуры (runtime + Render + CI/CD + ownership)


---

## 4) Render: целевая структура окружений

Минимум:
- `acc` — staging/acceptance (деплой при merge в main).
- `prd` — production (деплой только через approval).

Опционально:
- `dev` — песочница (ручной деплой с любой ветки).

### 4.1 Сервисы на окружение
На каждое окружение создаем набор:
- `*-backend` (FastAPI),
- `*-frontend` (frontend),
- `*-postgres` (managed Postgres),
- (если есть) `db-admin`, `cron-job` — только если реально нужно, иначе лишняя поверхность атаки.

### 4.2 Region и планы
Сейчас в `render.yaml` указано `region: frankfurt` и `plan: free`. Если меняете регион/план — фиксируйте в этом документе и в IaC (render.yaml), чтобы окружения были воспроизводимы.

---

## 5) Render IaC: как должен выглядеть render.yaml

Цель: чтобы Render-ресурсы создавались/обновлялись декларативно.

Текущее (важное из `render.yaml`):
- EnvVarGroup: `wiki-secrets` (OAUTH ключи, `sync:false`).
- Database: `wiki-db`, `databaseName: wiki`.
- Service API: `wiki-api`:
  - `DATABASE_URL` fromDatabase connectionString,
  - TTL переменные заданы значениями,
  - buildCommand тянет submodules через `GITHUB_USERNAME`/`GITHUB_ACCESS_TOKEN`,
  - startCommand делает `alembic upgrade head` и запускает FastAPI.
- Service frontend: `wiki-frontend`:
  - `VITE_API_URL` задан явно на публичный URL API.

### 5.1 Критичное: submodules и доступы к GitHub
Если buildCommand использует:
- `GITHUB_USERNAME`
- `GITHUB_ACCESS_TOKEN`

то это runtime/build-time секреты Render, и их нужно добавить в Env Group соответствующего окружения (или в service env). Эти значения не должны попадать в репозиторий.

---

## 6) Ownership env vars и секретов (обязательно)

### 6.1 Render Env Groups (runtime)
В Env Group каждого окружения храним:
- `OAUTH_NAME_APPLICATION_ID` (secret)
- `OAUTH_NAME_SECRET_KEY` (secret)
- `TOKEN_TTL_SECONDS` (config)
- `SESSION_TTL_SECONDS` (config)
- `GITHUB_USERNAME` (secret/config для submodules)
- `GITHUB_ACCESS_TOKEN` (secret для submodules)

`DATABASE_URL` задается из managed database, как в `render.yaml` (fromDatabase connectionString).

### 6.2 Render Service Env (локальные для сервиса)
Только сервисные параметры:
- `PORT` (если нужно вручную),
- flags, которые относятся только к одному сервису.

### 6.3 GitHub Secrets (CI/CD only)
Только секреты, нужные GitHub Actions для управления деплоем:
- `RENDER_DEPLOY_HOOK_ACC_BACKEND`
- `RENDER_DEPLOY_HOOK_ACC_FRONTEND`
- `RENDER_DEPLOY_HOOK_PRD_BACKEND`
- `RENDER_DEPLOY_HOOK_PRD_FRONTEND`

И (опционально) любые секреты CI (например, публикация артефактов), если они не являются runtime конфигом приложения.

---

## 7) GitHub Actions: модель деплоя на Render

Deploy hooks + GitHub Environments
- acc: деплой при merge в `main` (без ручного гейта)
- prd: деплой только через `workflow_dispatch`/tag + GitHub Environment approval

Это дает:
- управляемое продвижение релиза,
- аудит (кто аппрувнул),
- одинаковые правила для prod.

---

## 8) Пример workflow для deploy hooks (скелет)

Этот workflow **не добавлен** автоматически этим документом. Его нужно создать в монорепозитории (там где `render.yaml`) или в отдельном infra-репозитории.

Минимальный смысл:
- job `deploy_acc` дергает 2 hook URL (backend + frontend) на push в main,
- job `deploy_prd` дергает 2 hook URL только при manual trigger и после approval.

> Важно: hook URLs лежат в GitHub Secrets, не в коде.

---

## 9) Миграции на Render: риски и безопасный подход

### 9.1 Текущее состояние
В `render.yaml` у API startCommand включено:
- `alembic upgrade head` перед запуском приложения.

Это работает, но имеет риск: при параллельном старте нескольких инстансов миграции могут столкнуться.

### 9.2 Рекомендуемое решение (выбрать и закрепить)
Варианты:
- **Вариант 1 (простая дисциплина):** миграции выполняются “one-off” перед деплоем (ручной шаг или отдельный workflow step).
- **Вариант 2 (автоматизация):** миграции запускаются отдельным job/service “migrate”, который выполняется один раз на релиз (и/или использует advisory lock).

Статус: решение команды требуется. Пока — фиксируем риск и не считаем это “закрытым”.

---

## 10) Frontend на Render: важная деталь

В `render.yaml` для frontend startCommand стоит `npm run dev`.

Для production окружения обычно нужно:
- `npm run build` и раздача статикой (или render static site),
- иначе вы держите dev-server в проде (медленно, нестабильно, лишние зависимости).

Решение: либо перевод фронта на static site (рекомендуется), либо явный production server (`npm run preview`/node server), но не `dev`.

Статус: требует решения команды и корректировки `render.yaml`.
