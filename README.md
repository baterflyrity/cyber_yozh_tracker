# CyberYozh Task Manager

Веб-приложение для управления задачами: REST API на **Django 5.2 LTS + Django REST Framework**, JWT-аутентификация, OpenAPI-документация (Swagger UI / Redoc) и встроенный браузерный интерфейс на Django templates + vanilla JavaScript с темами **Системная / Светлая / Тёмная**.

Одна команда `docker compose up --build` поднимает приложение с миграциями и идемпотентными демо-данными. Отдельный контейнер БД не нужен: используется SQLite в именованном Docker volume.

---

## Содержание

1. [Функциональность](#1-функциональность)
2. [Демонстрация UI](#2-демонстрация-ui)
3. [Быстрый запуск через Docker Compose](#3-быстрый-запуск-через-docker-compose)
4. [Демо-данные](#4-демо-данные)
5. [Пошаговый E2E-сценарий (curl)](#5-пошаговый-e2e-сценарий-curl)
6. [UI smoke-check](#6-ui-smoke-check)
7. [Запуск тестов и линтера](#7-запуск-тестов-и-линтера)
8. [Полезные Docker-команды](#8-полезные-docker-команды)
9. [Запуск без Docker](#9-запуск-без-docker)
10. [API reference](#10-api-reference)
11. [Правила доступа](#11-правила-доступа)
12. [Структура проекта](#12-структура-проекта)
13. [Конфигурация и безопасность](#13-конфигурация-и-безопасность)
14. [Известные ограничения](#14-известные-ограничения)
15. [Статус проверки этой сборки](#15-статус-проверки-этой-сборки)
16. [Документация](#16-документация)

---

## 1. Функциональность

- Регистрация с уникальным `username` и необязательным уникальным `email`; пароли хешируются штатными средствами Django и никогда не возвращаются в ответах API.
- JWT: выдача пары `access`/`refresh`, обновление `access` по `refresh`, endpoint текущего пользователя.
- Задачи: `title` (1–200), `description`, `created_by` (задаётся сервером), `assigned_to` (активный пользователь или `null`), `is_completed`, `created_at`, `updated_at`; полный CRUD.
- Справочник пользователей `GET /api/users/?search=` для назначения исполнителя (только `id` и `username`).
- Комментарии во вложенном URL `/api/tasks/{task_id}/comments/`, каскадное удаление с задачей.
- Фильтр `?is_completed=true|false`, поиск `?search=` по заголовку и описанию, сортировка `?ordering=` (поля `created_at`, `updated_at`, `title`, `is_completed`), пагинация по 20 элементов (`page`, `page_size`, максимум 100).
- OpenAPI-схема и интерактивная документация.
- Браузерный интерфейс: список/поиск/фильтры задач, создание, редактирование, назначение, смена статуса, удаление с подтверждением, комментарии, состояния загрузки/ошибки/пустого списка, адаптивная вёрстка и три режима темы с запоминанием выбора.
- Docker Compose: миграции → идемпотентный seed → development server.

**Стек:** Python 3.12, Django 5.2 LTS, Django REST Framework, djangorestframework-simplejwt, drf-spectacular, SQLite, uv (зависимости и lock-файл), pytest + pytest-django, Ruff.

## 2. Демонстрация UI

После запуска откройте:

| Страница | Адрес |
|---|---|
| Рабочая область задач | http://localhost:8000/ |
| Вход | http://localhost:8000/login/ |
| Регистрация | http://localhost:8000/register/ |
| Детали задачи | http://localhost:8000/tasks/`<id>`/ |
| Swagger UI | http://localhost:8000/api/docs/ |
| Redoc | http://localhost:8000/api/redoc/ |
| OpenAPI schema | http://localhost:8000/api/schema/ |

Краткий сценарий: зарегистрируйтесь (или войдите под `demo_owner`) → нажмите **«Создать задачу»** → в диалоге заполните заголовок, описание и исполнителя → откройте задачу из списка → отметьте выполненной, отредактируйте или добавьте комментарий → переключите тему в шапке (селектор **Системная / Светлая / Тёмная**, выбор сохраняется в `localStorage` и применяется до первой отрисовки).

## 3. Быстрый запуск через Docker Compose

**Требования:** Docker Engine 20.10+ (или Docker Desktop) с плагином Docker Compose v2 (`docker compose version` должен вернуть версию). Других зависимостей не нужно.

```bash
# 1. клонировать репозиторий и перейти в него
git clone <repo-url> cyberyozh-task-manager
cd cyberyozh-task-manager

# 2. собрать образы и запустить приложение
docker compose up --build
```

Что происходит при старте (см. `docker/entrypoint.sh`):

1. создаётся каталог для SQLite-файла (`/app/data` в именованном volume);
2. применяются миграции — `python manage.py migrate --noinput` (ошибка миграций останавливает контейнер с ненулевым кодом);
3. при `SEED_DEMO_DATA=1` выполняется `python manage.py seed_demo_data` (идемпотентно, см. раздел 4);
4. запускается development server на `0.0.0.0:8000`.

Ожидаемое состояние: сервис `web` запущен, в логах видны строки `Applying database migrations`, `Demo data is up to date.` и `Starting development server on 0.0.0.0:8000`, а `curl -I http://localhost:8000/` возвращает `HTTP/1.1 200 OK`.

Приложение: http://localhost:8000/ · Swagger: http://localhost:8000/api/docs/ · Redoc: http://localhost:8000/api/redoc/ · Schema: http://localhost:8000/api/schema/

## 4. Демо-данные

Seed выполняется management-командой `python manage.py seed_demo_data` (не SQL из compose-файла) и **идемпотентен**: повторный запуск не создаёт дубликатов пользователей, задач и комментариев, пароли уже существующих пользователей не меняются. Команда **отказывается работать при `DJANGO_DEBUG=false`** и не запускается автоматически вне локальной Compose-конфигурации (`SEED_DEMO_DATA=1` выставлен только в `compose.yaml`).

| Username | Пароль | Роль в сценариях |
|---|---|---|
| `demo_owner` | `DemoOwner123!` | Создаёт задачи и управляет ими |
| `demo_worker` | `DemoWorker123!` | Исполнитель: может менять только статус |
| `demo_outsider` | `DemoOutsider123!` | Посторонний: проверяет запрет доступа |

Создаваемые задачи:

| Задача | Создана | Назначена | Назначение в сценарии |
|---|---|---|---|
| «Подготовить демонстрационный API-сценарий» | `demo_owner` | `demo_worker` | Основной E2E-сценарий |
| «Задача только для владельца» | `demo_owner` | — | `demo_worker`/`demo_outsider` не должны её видеть |
| «Моя задача исполнителя» | `demo_worker` | — | Работа со своей задачей |

К первой задаче добавлены два комментария — от `demo_owner` и от `demo_worker`.

> ⚠️ **Эти пароли предназначены только для локального тестового окружения.** Не используйте их вне локальной разработки и не выкладывайте такой набор в production.

## 5. Пошаговый E2E-сценарий (curl)

Примеры рассчитаны на bash/zsh (в Windows — Git Bash). Приложение запущено на `http://localhost:8000`.

```bash
BASE=http://localhost:8000
```

### 5.1. Вход владельца и список задач (ожидаем `200`)

```bash
OWNER=$(curl -s -X POST $BASE/api/auth/token/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"demo_owner","password":"DemoOwner123!"}')
OWNER_ACCESS=$(echo "$OWNER" | python3 -c 'import sys,json;print(json.load(sys.stdin)["access"])')

curl -s -o /dev/null -w '%{http_code}\n' $BASE/api/tasks/ -H "Authorization: Bearer $OWNER_ACCESS"
# 200 — в ответе только задачи, созданные demo_owner или назначенные ему
```

Скопировать токен вручную тоже можно: залогиньтесь через Swagger UI (**Authorize** → схема `bearerAuth`) или возьмите `access` из ответа `POST /api/auth/token/`. В curl подставляйте его в заголовок `Authorization: Bearer <access token>` (рекомендуется держать его в shell-переменной, как выше, — токены не должны попадать в историю команд в открытом виде и в URL).

### 5.2. Просмотр задачи и комментарий от владельца (ожидаем `200`, `201`)

```bash
curl -s $BASE/api/tasks/1/ -H "Authorization: Bearer $OWNER_ACCESS" | python3 -m json.tool
# 200: created_by = demo_owner, assigned_to = {"id": 2, "username": "demo_worker"}, is_completed = false

curl -s -o /dev/null -w '%{http_code}\n' -X POST $BASE/api/tasks/1/comments/ \
  -H "Authorization: Bearer $OWNER_ACCESS" -H 'Content-Type: application/json' \
  -d '{"body":"E2E: проверка комментария владельца"}'
# 201
```

### 5.3. Исполнитель меняет только статус (ожидаем `200`)

```bash
WORKER=$(curl -s -X POST $BASE/api/auth/token/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"demo_worker","password":"DemoWorker123!"}')
WORKER_ACCESS=$(echo "$WORKER" | python3 -c 'import sys,json;print(json.load(sys.stdin)["access"])')

curl -s -o /dev/null -w '%{http_code}\n' -X PATCH $BASE/api/tasks/1/ \
  -H "Authorization: Bearer $WORKER_ACCESS" -H 'Content-Type: application/json' \
  -d '{"is_completed":true}'
# 200 — исполнителю разрешён только is_completed
```

### 5.4. Запрещённые действия исполнителя (ожидаем `403`)

```bash
curl -s -w '\n%{http_code}\n' -X PATCH $BASE/api/tasks/1/ \
  -H "Authorization: Bearer $WORKER_ACCESS" -H 'Content-Type: application/json' \
  -d '{"title":"hacked"}'
# {"detail":"Assignee may only change the completion status of the task."}  →  403

curl -s -o /dev/null -w '%{http_code}\n' -X PATCH $BASE/api/tasks/1/ \
  -H "Authorization: Bearer $WORKER_ACCESS" -H 'Content-Type: application/json' \
  -d '{"assigned_to":3}'      # 403 — переназначение доступно только создателю
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE $BASE/api/tasks/1/ \
  -H "Authorization: Bearer $WORKER_ACCESS"   # 403 — удаление доступно только создателю
```

### 5.5. Посторонний пользователь не видит чужую задачу (ожидаем `404`)

```bash
OUT=$(curl -s -X POST $BASE/api/auth/token/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"demo_outsider","password":"DemoOutsider123!"}')
OUT_ACCESS=$(echo "$OUT" | python3 -c 'import sys,json;print(json.load(sys.stdin)["access"])')

curl -s $BASE/api/tasks/ -H "Authorization: Bearer $OUT_ACCESS" | python3 -m json.tool
# 200, но results не содержит задачу с id=1 (только собственные задачи)
curl -s -o /dev/null -w '%{http_code}\n' $BASE/api/tasks/1/ -H "Authorization: Bearer $OUT_ACCESS"   # 404
curl -s -o /dev/null -w '%{http_code}\n' -X POST $BASE/api/tasks/1/comments/ \
  -H "Authorization: Bearer $OUT_ACCESS" -H 'Content-Type: application/json' \
  -d '{"body":"intrusion"}'   # 404
```

Ответы `404` выбраны вместо `403` для объектов вне доступного queryset, чтобы не раскрывать факт существования чужой задачи; запреты **внутри** доступного набора возвращают `403`. Поведение последовательно и продублировано в OpenAPI-описании.

### 5.6. Комментарии: редактирует только автор (ожидаем `403`/`200`)

```bash
curl -s $BASE/api/tasks/1/comments/ -H "Authorization: Bearer $OWNER_ACCESS" | python3 -m json.tool
# возьмите id первого комментария, например 1
CID=1

curl -s -o /dev/null -w '%{http_code}\n' -X PATCH $BASE/api/tasks/1/comments/$CID/ \
  -H "Authorization: Bearer $WORKER_ACCESS" -H 'Content-Type: application/json' \
  -d '{"body":"hijacked"}'    # 403 — не автор
curl -s -o /dev/null -w '%{http_code}\n' -X PATCH $BASE/api/tasks/1/comments/$CID/ \
  -H "Authorization: Bearer $OUT_ACCESS" -H 'Content-Type: application/json' \
  -d '{"body":"hijacked"}'    # 404 — нет доступа к задаче
curl -s -o /dev/null -w '%{http_code}\n' -X PATCH $BASE/api/tasks/1/comments/$CID/ \
  -H "Authorization: Bearer $OWNER_ACCESS" -H 'Content-Type: application/json' \
  -d '{"body":"E2E: комментарий обновлён владельцем"}'   # 200
```

### 5.7. Регистрация, refresh-токен и валидация (ожидаем `201`, `200`, `400`, `401`)

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST $BASE/api/auth/register/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"e2e_user","password":"E2e-Str0ng-Pass!"}'   # 201

curl -s -o /dev/null -w '%{http_code}\n' -X POST $BASE/api/auth/token/refresh/ \
  -H 'Content-Type: application/json' \
  -d "{\"refresh\":\"$REFRESH\"}"                              # 200

curl -s -o /dev/null -w '%{http_code}\n' -X POST $BASE/api/tasks/ \
  -H "Authorization: Bearer $OWNER_ACCESS" -H 'Content-Type: application/json' \
  -d '{"title":"  "}'                                           # 400 — пустой заголовок
curl -s -o /dev/null -w '%{http_code}\n' -X POST $BASE/api/tasks/ \
  -H "Authorization: Bearer $OWNER_ACCESS" -H 'Content-Type: application/json' \
  -d '{"title":"x","assigned_to":999999}'                       # 400 — несуществующий пользователь
curl -s -o /dev/null -w '%{http_code}\n' "$BASE/api/tasks/?is_completed=maybe" \
  -H "Authorization: Bearer $OWNER_ACCESS"                      # 400 — неверный фильтр

curl -s -o /dev/null -w '%{http_code}\n' $BASE/api/tasks/      # 401 — без токена
```

(Для `refresh` подставьте свой `refresh` из ответа входа: `REFRESH=$(echo "$OWNER" | python3 -c 'import sys,json;print(json.load(sys.stdin)["refresh"])')`.)

## 6. UI smoke-check

Ручная браузерная проверка. Ширины: ~375 px (телефон), 768 px (планшет), ~1440 px (desktop) — горизонтальной прокрутки страницы быть не должно, формы и кнопки не должны обрезаться.

1. `/`, `/login/`, `/register/` открываются; без входа список задач показывает приглашение войти, защищённые данные не отображаются.
2. Вход `demo_owner` открывает список его задач; в шапке видно имя пользователя; **Выйти** очищает состояние и возвращает на `/login/`.
3. Создание задачи (заголовок + описание + исполнитель) → карточка появляется в списке; открытие задачи показывает описание, автора, исполнителя, статус и даты.
4. Редактирование заголовка/описания и удаление с подтверждением — только у создателя; у исполнителя переключается только статус.
5. Назначение исполнителя из справочника и снятие назначения (`— не назначен —`).
6. Добавление комментария, редактирование и удаление собственного комментария; чужой комментарий без кнопок (сервер всё равно отклонит запрос).
7. Поиск, фильтр «Все / Не выполнена / Выполнена» и сортировка; пустой список и состояние ошибки с кнопкой «Повторить» показываются корректно; невалидные поля подсвечиваются сообщениями рядом с полем.
8. Темы **Системная / Светлая / Тёмная**: переключение без перезагрузки, выбор сохраняется после перезагрузки, «Системная» реагирует на смену темы ОС; контраст читаем в обеих темах, focus виден при навигации с клавиатуры.
9. Мобильная ширина: шапка переносится, фильтры складываются в колонку, карточки идут в одну колонку, диалог создания/редактирования помещается на экран и закрывается клавишей Escape.

## 7. Запуск тестов и линтера

**Вне Docker** (нужен uv — https://docs.astral.sh/uv/):

```bash
uv sync                     # установить зависимости (включая dev-группу)
uv run pytest               # 60 тестов
uv run ruff check .         # линтер
uv run python manage.py makemigrations --check --dry-run   # миграции синхронизированы
```

Ожидаемый результат: `60 passed`, `All checks passed!`, `No changes detected`.

Что покрывают тесты:

- регистрация, выдача и обновление JWT, `/api/auth/me/`, справочник пользователей;
- неаутентифицированный доступ к задачам и комментариям (`401`);
- `created_by` берётся из текущего пользователя и не подменяется из payload;
- CRUD задачи создателем (чтение/обновление/удаление);
- исполнитель видит задачу и меняет только `is_completed`; попытки менять `title`/`description`/`assigned_to` и удалять → `403`;
- посторонний не видит задачу в списке и получает `404` по detail;
- назначение существующего активного пользователя, ошибки для неизвестного/неактивного (`400`);
- фильтр `is_completed`, поиск, сортировка, пагинация (страница по 20);
- участники читают и создают комментарии, посторонние получают `404`;
- изменение/удаление комментария только автором; вложенный `task_id` проверяется (нельзя достать комментарий через чужую задачу);
- валидация заголовка (1–200) и тела комментария (1–5000), `PUT` для комментариев не поддерживается (`405`);
- доступность `/api/schema/`, `/api/docs/`, `/api/redoc/` и наличие `bearerAuth` в схеме;
- страницы `/`, `/login/`, `/register/`, `/tasks/<id>/` и разрешаемость всех static-assets;
- идемпотентность `seed_demo_data`, сохранение существующих паролей, отсутствие `is_staff`/`is_superuser` у демо-аккаунтов и отказ команды при `DEBUG=false`.

**Внутри контейнера:**

```bash
docker compose exec web pytest
docker compose exec web ruff check .
```

## 8. Полезные Docker-команды

```bash
docker compose up --build        # сборка и запуск (миграции + seed + сервер)
docker compose logs -f web       # логи сервиса (Ctrl+C — выход из просмотра)
docker compose ps                # статус контейнеров
docker compose exec web pytest   # тесты в контейнере
docker compose exec web ruff check .
docker compose exec web python manage.py shell   # Django shell
docker compose down              # остановить, данные в volume сохраняются
docker compose down -v           # ПОЛНЫЙ СБРОС: удаляет volume с SQLite-базой
```

> ⚠️ `docker compose down -v` удаляет именованный volume `cyberyozh_data` вместе с SQLite-файлом. Следующий `docker compose up --build` создаст чистую базу, применит миграции заново и заново загрузит демо-данные.

Повторный запуск после `docker compose down` (без `-v`) не создаёт дубликатов: seed использует `get_or_create` по стабильным username/заголовкам.

## 9. Запуск без Docker

**Требования:** Python 3.12+ и [uv](https://docs.astral.sh/uv/getting-started/installation/) (или обычный `pip`).

```bash
# 1. окружение и зависимости
uv sync                       # альтернатива без uv: python3.12 -m venv .venv && . .venv/bin/activate && pip install django djangorestframework djangorestframework-simplejwt drf-spectacular pytest pytest-django ruff

# 2. переменные окружения
cp .env.example .env          # при желании отредактируйте значения
set -a && . ./.env && set +a  # bash/zsh: выгрузить .env в окружение
# PowerShell: Get-Content .env | ForEach-Object { $_ } | Where-Object {$_ -notmatch '^\s*#'} | ForEach-Object { $k,$v = $_.Split('=',2); Set-Item -Path "env:$k" -Value $v }

# 3. миграции и демо-данные (опционально, только для локальной разработки)
uv run python manage.py migrate
uv run python manage.py seed_demo_data

# 4. development server → http://localhost:8000/
uv run python manage.py runserver

# 5. тесты и линтер
uv run pytest
uv run ruff check .
```

Без `.env` приложение тоже запускается: используются значения по умолчанию из `config/settings.py` (`DJANGO_DEBUG=true`, SQLite в `./data/db.sqlite3`). Переменные см. таблицу в разделе 13.

Static-файлы в development отдаёт Django напрямую (`DEBUG=true`); для сбора в один каталог есть `uv run python manage.py collectstatic` (в Compose не используется).

## 10. API reference

| Документ | Адрес |
|---|---|
| OpenAPI schema | http://localhost:8000/api/schema/ |
| Swagger UI | http://localhost:8000/api/docs/ |
| Redoc | http://localhost:8000/api/redoc/ |

Аутентификация — HTTP Bearer: `Authorization: Bearer <access token>`.

| Метод | Endpoint | Доступ |
|---|---|---|
| `POST` | `/api/auth/register/` | публичный |
| `POST` | `/api/auth/token/` | публичный (JWT access/refresh) |
| `POST` | `/api/auth/token/refresh/` | по refresh token |
| `GET` | `/api/auth/me/` | аутентифицированный |
| `GET` | `/api/users/?search=` | аутентифицированный |
| `GET`, `POST` | `/api/tasks/` | аутентифицированный |
| `GET`, `PUT`, `PATCH`, `DELETE` | `/api/tasks/{id}/` | по правилам доступа |
| `GET`, `POST` | `/api/tasks/{task_id}/comments/` | участник задачи |
| `GET`, `PATCH`, `DELETE` | `/api/tasks/{task_id}/comments/{id}/` | участник задачи, изменения — автор |

Пагинация: `?page=`, `?page_size=` (по умолчанию 20, максимум 100), формат ответа `{"count", "next", "previous", "results"}`.

Формат ошибок — стандартный DRF: `400` `{"<поле>": ["сообщение"]}` или `{"detail": [...]}`, `401`/`403` — `{"detail": "..."}`, `404` — `{"detail": "..."}`.

## 11. Правила доступа

| Субъект | Может |
|---|---|
| Любой аутентифицированный пользователь | создать задачу (`created_by` задаётся сервером), видеть только свои задачи и назначенные ему |
| Создатель задачи | читать, менять `title`, `description`, `assigned_to`, `is_completed`, удалять задачу, управлять комментариями как автор |
| Исполнитель | читать задачу и её комментарии, добавлять комментарии, менять **только** `is_completed` |
| Участник (создатель/исполнитель) | просматривать и добавлять комментарии |
| Автор комментария | редактировать и удалять свой комментарий, пока остаётся участником задачи |
| Посторонний | ничего: задача отсутствует в списке и отдаёт `404` по detail и по вложенным комментариям |

После переназначения прежний исполнитель теряет доступ (если не является создателем). Объекты вне доступного queryset → `404`, запрещённая операция внутри набора → `403`. Правила реализованы на сервере в `apps/tasks/services.py` + `apps/tasks/selectors.py`; скрытие кнопок в UI — только UX.

## 12. Структура проекта

```text
.
├── AGENTS.md, spec/            # исходные документы требований
├── config/                     # settings, urls, wsgi/asgi, пагинация, обработчик ошибок
├── apps/
│   ├── users/
│   │   ├── services.py         # регистрация пользователя
│   │   ├── selectors.py        # справочник активных пользователей
│   │   └── api/                # serializers, views, urls (register/token/me/users)
│   │   └── tests/              # тесты аутентификации и справочника
│   └── tasks/
│       ├── models.py           # Task, Comment (структура и связи)
│       ├── services.py         # бизнес-правила: создание/правка/удаление, комментарии
│       ├── selectors.py        # видимость задач, фильтры/поиск/сортировка, комментарии
│       ├── api/                # serializers, permissions, views, urls
│       ├── management/commands/seed_demo_data.py
│       ├── migrations/
│       └── tests/              # тесты CRUD, доступа, комментариев, docs, seed
├── web/                        # только HTML page views (shell), без бизнес-логики
├── templates/                  # base, dashboard, login, register, task_detail
├── static/css/styles.css       # дизайн-токены и компоненты, light/dark
├── static/js/                  # theme.js, ui.js, api.js, pages/* (vanilla JS)
├── docs/ARCHITECTURE.md        # описание реализованной архитектуры
├── docker/entrypoint.sh        # migrate → seed → runserver
├── Dockerfile, compose.yaml, .dockerignore, .env.example
├── pyproject.toml, uv.lock, .python-version
└── README.md
```

Направление зависимостей: `web views → templates`, `API views → serializers/selectors/services → models`; модели ничего не импортируют из API, сервисы не знают о HTTP/DRF, selectors не формируют ответы.

## 13. Конфигурация и безопасность

| Переменная | Назначение | Значение по умолчанию |
|---|---|---|
| `DJANGO_DEBUG` | режим отладки; `false` блокирует seed и требует настоящего ключа | `true` |
| `DJANGO_SECRET_KEY` | секретный ключ Django | небезопасный dev-ключ (допустимо только при `DEBUG=true`) |
| `DJANGO_ALLOWED_HOSTS` | список хостов через запятую | `localhost,127.0.0.1` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | доверенные origin'ы для CSRF | пусто |
| `DJANGO_DB_PATH` | путь к SQLite-файлу | `./data/db.sqlite3` (в Compose: `/app/data/db.sqlite3`) |
| `SEED_DEMO_DATA` | `1` — запускать seed из entrypoint | `0` (`1` в `compose.yaml`) |

Безопасность и гигиена:

- `.env` в git не коммитится (см. `.gitignore`); в репозитории только `.env.example` без секретов.
- `.dockerignore` исключает `.git`, `.venv`, кэши, `.env` и локальную БД из образа.
- Пароли хранятся только в хеше Django; в API-ответах нет ни паролей, ни хешей, ни stack trace.
- JWT хранится в `sessionStorage` вкладки; при истечении `access` выполняется максимум одна попытка refresh и один повтор запроса, затем состояние очищается и пользователь возвращается на `/login/`. Токены не попадают в URL, HTML и логи.
- Демо-seed заблокирован при `DEBUG=false`; демо-пароли — только для локального окружения.
- Пользовательский текст в DOM вставляется через `textContent`/создание узлов, без `innerHTML`.

## 14. Известные ограничения

- SQLite и development server (`runserver`) рассчитаны на локальную разработку и проверку задания, **не для production**.
- Compose содержит один сервис (`web`); отдельного контейнера БД, Redis, Celery и фронтенд-сервиса нет — по условию они не нужны.
- Поиск `?search=` использует `icontains`; SQLite регистронезависимо обрабатывает только ASCII, поэтому для кириллицы дополнительно перебираются варианты регистра (`lower`/`upper`/`capitalize`/`title`). Полный case-insensitive поиск для всех языков потребовал бы расширения ICU или другой СУБД.
- Email делает необязательным, но задаёт уникальность (case-insensitive) — как требует спецификация.
- Real-time обновления, уведомления, вложения и админ-консоль в UI не реализованы — их нет в задании.
- Для комментариев поддерживается `PATCH`, `PUT` возвращается `405` (допускается спецификацией).

## 15. Статус проверки этой сборки

Фактически выполнено в среде разработки этой сборки:

| Проверка | Команда | Результат |
|---|---|---|
| Тесты | `uv run pytest` | **60 passed** |
| Линтер | `uv run ruff check .` | **All checks passed** |
| Миграции на чистой БД | `uv run python manage.py migrate` | применены, включая `tasks.0001_initial` |
| Нет незапрошенных миграций | `uv run python manage.py makemigrations --check --dry-run` | `No changes detected` |
| Идемпотентность seed | `uv run python manage.py seed_demo_data` ×2 | вторая итерация не создаёт дубликатов |
| Генерация схемы | `uv run python manage.py spectacular --file schema.yaml` | exit 0, 0 ошибок, 0 предупреждений |
| HTTP-сценарий E2E | live `runserver` + `curl` по разделам 5.1–5.7 | все ожидаемые статусы получены (200/201/400/401/403/404) |
| Страницы и static | `curl` по `/`, `/login/`, `/register/`, `/tasks/1/`, `/api/docs/`, `/api/redoc/`, `/api/schema/`, CSS/JS | все `200` |
| Синтаксис JS | `node --check` по всем файлам `static/js` | OK |

**Не выполнялось в этой среде** (ограничения окружения: нет Docker и нет браузера):

- `docker compose up --build` и повторный запуск/`down -v` — команды приведены по фактическим `compose.yaml`/`docker/entrypoint.sh`, но в контейнерах не запускались;
- ручной браузерный UI smoke-check из раздела 6 — выполняется проверяющим; серверная часть сценариев (API, страницы, статика) проверена HTTP-запросами, логика тем — кодом и статической проверкой.

## 16. Документация

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — реализованная архитектура, слои и потоки данных.
- [`spec/`](spec/) — исходные документы требований (`SPEC.md`, `ARCHITECTURE.md`, `LOCAL_DEVELOPMENT.md`, `FRONTEND.md`, `DOCUMENTATION.md`).
- `AGENTS.md` — инструкции для coding agent.
