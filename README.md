# CyberYozh Task Manager

Веб-приложение для управления задачами: REST API на **Django 5.2 LTS + Django REST Framework**, JWT-аутентификация, OpenAPI-документация (Swagger UI / Redoc) и встроенный браузерный интерфейс на Django templates + vanilla JavaScript с темами **Системная / Светлая / Тёмная**.

Одна команда `docker compose up --build` поднимает приложение с миграциями и идемпотентными демо-данными. Отдельный контейнер БД не нужен: используется SQLite в именованном Docker volume. Браузерные E2E-тесты (Playwright) запускаются отдельным профилем Compose.

---

## Содержание

1. [Функциональность](#1-функциональность)
2. [Демонстрация UI](#2-демонстрация-ui)
3. [Быстрый запуск через Docker Compose](#3-быстрый-запуск-через-docker-compose)
4. [Демо-данные](#4-демо-данные)
5. [Пошаговый E2E-сценарий (curl)](#5-пошаговый-e2e-сценарий-curl)
6. [UI smoke-check](#6-ui-smoke-check)
7. [Запуск тестов и линтера](#7-запуск-тестов-и-линтера)
8. [Браузерные E2E-тесты (Playwright)](#8-браузерные-e2e-тесты-playwright)
9. [Полезные Docker-команды](#9-полезные-docker-команды)
10. [Запуск без Docker](#10-запуск-без-docker)
11. [API reference](#11-api-reference)
12. [Правила доступа](#12-правила-доступа)
13. [Структура проекта](#13-структура-проекта)
14. [Конфигурация и безопасность](#14-конфигурация-и-безопасность)
15. [Известные ограничения](#15-известные-ограничения)
16. [Типичные ошибки и их устранение](#16-типичные-ошибки-и-их-устранение)
17. [Документация](#17-документация)

---

## 1. Функциональность

- Регистрация с уникальным `username` и необязательным уникальным `email`; пароли хешируются штатными средствами Django и никогда не возвращаются в ответах API.
- JWT: выдача пары `access`/`refresh`, обновление `access` по `refresh`, endpoint текущего пользователя.
- Задачи: `title` (1–200), `description`, `created_by` (задаётся сервером), `assigned_to` (активный пользователь или `null`), `is_completed`, `created_at`, `updated_at`; полный CRUD.
- Справочник пользователей `GET /api/users/?search=` для назначения исполнителя (только `id` и `username`).
- Комментарии во вложенном URL `/api/tasks/{task_id}/comments/`, каскадное удаление с задачей.
- Фильтр `?is_completed=true|false`, поиск `?search=` по заголовку и описанию, сортировка `?ordering=` (поля `created_at`, `updated_at`, `title`, `is_completed`), пагинация по 20 элементов (`page`, `page_size`, максимум 100).
- OpenAPI-схема и интерактивная документация; Swagger UI и Redoc отдаются **локально** из пакета `drf-spectacular-sidecar` (пиненая версия, без CDN).
- Браузерный интерфейс: список/поиск/фильтры задач, создание, редактирование, назначение, смена статуса, удаление с подтверждением, комментарии, состояния загрузки/ошибки/пустого списка, адаптивная вёрстка и три режима темы с запоминанием выбора.
- Автоматические тесты: unit/integration (pytest) и браузерные E2E (Playwright, headless Chromium).
- Docker Compose: миграции → идемпотентный seed → development server; отдельный профиль `e2e` для браузерных тестов.

**Стек:** Python 3.12, Django 5.2 LTS, Django REST Framework, djangorestframework-simplejwt, drf-spectacular (+ sidecar), SQLite, uv (зависимости и lock-файл), pytest + pytest-django, Playwright for Python, Ruff.

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

**Требования:** Docker Engine 20.10+ (или Docker Desktop) с плагином Docker Compose v2 (`docker compose version` должен вернуть версию). Для браузерных E2E-тестов в контейнере дополнительно нужен только Docker — браузер ставится внутрь образа.

```bash
# 1. клонировать репозиторий и перейти в него
git clone https://github.com/baterflyrity/cyber_yozh_tracker.git
cd cyber_yozh_tracker

# 2. собрать образы и запустить приложение
docker compose up --build

# 3. (опционально) другой host-порт, если 8000 занят — например http://localhost:8001/
APP_PORT=8001 docker compose up --build
```

Host-порт настраивается переменной `APP_PORT` (по умолчанию `8000`, см. раздел 14):
`"${APP_PORT:-8000}:8000"` в `compose.yaml`. Внутри контейнера приложение всегда
слушает `0.0.0.0:8000`; Compose-имена контейнеров не зафиксированы (`container_name`
отсутствует), поэтому обычный запуск и изолированный тестовый проект можно
поднимать параллельно.

Что происходит при старте (см. `docker/entrypoint.sh`):

1. создаётся каталог для SQLite-файла (`/app/data` в именованном volume);
2. применяются миграции — `python manage.py migrate --noinput` (ошибка миграций останавливает контейнер с ненулевым кодом);
3. при `SEED_DEMO_DATA=1` выполняется `python manage.py seed_demo_data` (идемпотентно, см. раздел 4);
4. запускается development server на `0.0.0.0:8000`.

Ожидаемое состояние: сервис `web` запущен и проходит healthcheck (`docker compose ps` показывает `healthy`), в логах видны строки `Applying database migrations`, `Demo data is up to date.` и `Starting development server on 0.0.0.0:8000`, а `curl -I http://localhost:8000/` возвращает `HTTP/1.1 200 OK`.

Приложение: http://localhost:8000/ · Swagger: http://localhost:8000/api/docs/ · Redoc: http://localhost:8000/api/redoc/ · Schema: http://localhost:8000/api/schema/

При `APP_PORT=8001` замените `8000` на `8001` в host-адресах. Внутренний адрес
`http://web:8000` (для E2E-тестов внутри Compose-сети) от `APP_PORT` не зависит.
Для проверки готовности из хоста:

```bash
docker compose ps                                          # web должен быть healthy
curl --fail --show-error http://127.0.0.1:${APP_PORT:-8000}/api/schema/ -o /dev/null
```

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

REFRESH=$(echo "$OWNER" | python3 -c 'import sys,json;print(json.load(sys.stdin)["refresh"])')
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

## 6. UI smoke-check

Ручная браузерная проверка (часть сценариев автоматизирована в `tests/e2e`, раздел 8). Ширины: ~375 px (телефон), 768 px (планшет), ~1440 px (desktop) — горизонтальной прокрутки страницы быть не должно, формы и кнопки не должны обрезаться.

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
uv run pytest               # unit/integration: 60 тестов
uv run pytest tests/e2e     # браузерные E2E: 22 теста (нужен запущенный приложение + Chromium)
uv run ruff check .         # линтер
uv run python manage.py makemigrations --check --dry-run   # миграции синхронизированы
```

Ожидаемый результат: `60 passed` (+16 subtests), `22 passed`, `All checks passed!`, `No changes detected` — проверено в этом окружении: `pytest` → exit 0, `ruff check .` → exit 0, `makemigrations --check --dry-run` → exit 0, изолированный Compose E2E → `22 passed`, exit 0 (два последовательных прогона на чистом volume).

`uv run pytest` по умолчанию запускает только unit/integration-тесты (`testpaths = ["apps", "web"]` в `pyproject.toml`); браузерные тесты запускаются явно по пути `tests/e2e`.

Что покрывают unit/integration-тесты:

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

CI (`.github/workflows/ci.yml`) запускает обе проверки при `push` и `pull request`: unit/integration напрямую, E2E — через Docker Compose с выгрузкой артефактов Playwright при падении.

## 8. Браузерные E2E-тесты (Playwright)

Тесты в `tests/e2e/` открывают приложение в **настоящем headless Chromium** и проверяют сценарии пользователя, права доступа, адаптивность, темы и страницы документации API. Каждый тест использует независимый браузерный контекст и создаёт собственные данные (удаляются после теста), поэтому тесты можно запускать повторно.

### 8.1. Предварительные требования

- запущенное приложение (`docker compose up --build` **или** `uv run python manage.py runserver`);
- установленные зависимости (`uv sync`);
- установленный браузер: `uv run playwright install chromium`
  (в Linux можно добавить `--with-deps` для системных библиотек;
  в Docker-профиле `e2e` браузер уже входит в образ).

Переменные окружения:

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `E2E_BASE_URL` | origin приложения под тестом | `http://127.0.0.1:8000` |
| `E2E_READY_TIMEOUT` | сколько секунд ждать готовности приложения | `60` |

### 8.2. Запуск локально

```bash
docker compose up --build            # в одном терминале: приложение
uv run playwright install chromium   # однократно: браузер
uv run pytest tests/e2e              # в другом терминале: тесты
```

Если приложение не запущено, набор завершится с понятным сообщением
`Application is not reachable at ...` — поднимите приложение и повторите.

### 8.3. Предпочтительный запуск: Docker Compose (профиль `e2e`)

Обычный запуск (приложение + тесты в одном проекте):

```bash
docker compose --profile e2e up --build --exit-code-from e2e
```

Что происходит: собирается образ приложения и образ тестирования (`Dockerfile.e2e`, официальный образ Playwright `mcr.microsoft.com/playwright/python:v1.64.1-noble` с уже установленным headless Chromium — тег совпадает с пином `playwright==1.64.1` в `pyproject.toml`/`uv.lock`); сервис `e2e` стартует **только после healthcheck сервиса `web`** (`condition: service_healthy`), то есть после применения миграций и загрузки демо-данных; тесты обращаются к приложению по имени сервиса `E2E_BASE_URL=http://web:8000` внутри Compose-сети; `--exit-code-from e2e` возвращает код pytest (падение тестов не превращается в успех).

**Изолированный прогон** (рекомендуется: отдельное имя проекта, чистый project-scoped volume и настраиваемый порт — не трогает обычный локальный стек):

```bash
mkdir -p test-results

# Очистить только предыдущий тестовый проект и его volume
# (имя проекта cyberyozh-e2e зарезервировано только для тестов).
docker compose -p cyberyozh-e2e --profile e2e down -v --remove-orphans

# Собрать образы, поднять web, дождаться healthcheck, запустить Chromium и pytest.
APP_PORT=8001 docker compose -p cyberyozh-e2e --profile e2e up \
  --build --abort-on-container-exit --exit-code-from e2e
```

Успех — это фактический exit code `0` и строка `22 passed` в выводе pytest (проверено дважды подряд на чистом volume). Порт `8001` выбирается свободным из диапазона 8000–8010 и нужен только для доступа к UI снаружи; внутренний адрес тестов `http://web:8000` от него не зависит.

Если прогон упал — **до очистки** соберите диагностику:

```bash
docker compose -p cyberyozh-e2e --profile e2e ps -a
docker compose -p cyberyozh-e2e --profile e2e logs --no-color web e2e
find test-results -maxdepth 4 -type f -print   # скриншоты/трассировки упавших тестов
```

Очистка (только выделенный тестовый проект; volume с данными обычного запуска не затрагивается):

```bash
docker compose -p cyberyozh-e2e --profile e2e down -v --remove-orphans
```

Обычный запуск останавливается без удаления данных: `docker compose --profile e2e down` (volume с SQLite сохраняется, `down -v` — удаляет).

### 8.4. Какие сценарии покрыты

| Файл | Сценарии |
|---|---|
| `tests/e2e/test_auth_pages.py` | страницы для анонимного пользователя, ошибка неверного пароля, обязательные поля, вход `demo_owner`, поиск демо-задачи, выход и очистка состояния, валидация и создание аккаунта |
| `tests/e2e/test_task_workflow.py` | создание задачи через диалог (с валидацией), просмотр карточки, редактирование описания, назначение исполнителя, смена статуса в обе стороны, добавление и редактирование комментария, удаление с подтверждением, поиск/фильтр/сортировка, пустое состояние |
| `tests/e2e/test_access_rights.py` | исполнитель меняет только статус (кнопки скрыты **и** API отвечает `403`, данные не меняются), посторонний не видит чужую задачу (`404` по detail, в списке и для комментариев), редактирование/удаление комментария только автором, запрет переназначения |
| `tests/e2e/test_responsive_themes.py` | viewport 390×844 и 1440×900: отсутствие горизонтальной прокрутки, доступность основных действий, размер диалога; три режима темы, их визуальное отличие, сохранение после перезагрузки, реакция «Системной» на `prefers-color-scheme` |
| `tests/e2e/test_api_docs.py` | Redoc: контент документации, загрузка схемы, локальная версия бандла без CDN, отсутствие JS-ошибок; Swagger UI smoke; валидность `/api/schema/` |

Каждый тест дополнительно проверяет отсутствие необработанных JavaScript-ошибок, неожиданных ошибок консоли и сбойных сетевых запросов. Сознательно вызванные HTTP-статусы (`400`/`401`/`404`) тесты перечисляют явно в `allow_http_statuses` — любые другие ошибки консоли остаются падением.

### 8.5. Отчёты, скриншоты и трассировки

Настройки заданы в `pyproject.toml` (`[tool.pytest.ini_options] addopts`): скриншот при падении (`--screenshot=only-on-failure`), Playwright trace (`--tracing=retain-on-failure`) и видео (`--video=retain-on-failure`), каталог артефактов — `test-results/`.

```bash
uv run pytest tests/e2e                 # локально: артефакты в ./test-results/
docker compose --profile e2e up --build --exit-code-from e2e   # в Compose: тот же ./test-results (bind mount)

# просмотр трассировки после падения:
uv run playwright show-trace test-results/<имя-теста>/trace.zip
```

Каталог `test-results/` добавлен в `.gitignore` и `.dockerignore` — в git он не попадает. В GitHub Actions артефакты выгружаются действием `actions/upload-artifact` при падении job'а `e2e`.

> ⚠️ pytest-playwright **удаляет весь каталог `test-results/` в начале каждого прогона** (`delete_output_dir`). Собирайте скриншоты/трассировки сразу после падения и до следующего запуска. Сессионные логи Compose/pytest держите вне этого каталога — в `logs/` (в `.gitignore`).

## 9. Полезные Docker-команды

```bash
docker compose up --build        # сборка и запуск (миграции + seed + сервер)
APP_PORT=8001 docker compose up --build -d   # то же на другом host-порту
docker compose logs -f web       # логи сервиса (Ctrl+C — выход из просмотра)
docker compose ps                # статус контейнеров (web должен быть healthy)
docker compose exec web pytest   # unit/integration тесты в контейнере
docker compose exec web ruff check .
docker compose exec web python manage.py shell   # Django shell
docker compose --profile e2e up --build --exit-code-from e2e   # браузерные E2E
# изолированный E2E-прогон на чистом volume (см. раздел 8.3):
docker compose -p cyberyozh-e2e --profile e2e down -v --remove-orphans
APP_PORT=8001 docker compose -p cyberyozh-e2e --profile e2e up --build --abort-on-container-exit --exit-code-from e2e
docker compose down              # остановить, данные в volume сохраняются
docker compose down -v           # ПОЛНЫЙ СБРОС: удаляет volume с SQLite-базой
```

> ⚠️ `docker compose down -v` удаляет именованный volume `cyberyozh_data` вместе с SQLite-файлом. Следующий `docker compose up --build` создаст чистую базу, применит миграции заново и заново загрузит демо-данные.

Повторный запуск после `docker compose down` (без `-v`) не создаёт дубликатов: seed использует `get_or_create` по стабильным username/заголовкам.

## 10. Запуск без Docker

**Требования:** Python 3.12+ и [uv](https://docs.astral.sh/uv/getting-started/installation/) (или обычный `pip`).

```bash
# 1. окружение и зависимости
uv sync                       # альтернатива без uv: python3.12 -m venv .venv && . .venv/bin/activate && pip install django djangorestframework djangorestframework-simplejwt drf-spectacular drf-spectacular-sidecar pytest pytest-django ruff playwright pytest-playwright

# 2. переменные окружения
cp .env.example .env          # при желании отредактируйте значения
set -a && . ./.env && set +a  # bash/zsh: выгрузить .env в окружение
# PowerShell: Get-Content .env | Where-Object {$_ -notmatch '^\s*#'} | ForEach-Object { $k,$v = $_.Split('=',2); Set-Item -Path "env:$k" -Value $v }

# 3. миграции и демо-данные (опционально, только для локальной разработки)
uv run python manage.py migrate
uv run python manage.py seed_demo_data

# 4. development server → http://localhost:8000/
uv run python manage.py runserver

# 5. тесты и линтер
uv run pytest
uv run ruff check .

# 6. браузерные E2E (однократно ставится Chromium)
uv run playwright install chromium
uv run pytest tests/e2e
```

Без `.env` приложение тоже запускается: используются значения по умолчанию из `config/settings.py` (`DJANGO_DEBUG=true`, SQLite в `./data/db.sqlite3`). Переменные см. таблицу в разделе 14.

Static-файлы в development отдаёт Django напрямую (`DEBUG=true`); для сбора в один каталог есть `uv run python manage.py collectstatic` (в Compose не используется).

## 11. API reference

| Документ | Адрес |
|---|---|
| OpenAPI schema | http://localhost:8000/api/schema/ |
| Swagger UI | http://localhost:8000/api/docs/ |
| Redoc | http://localhost:8000/api/redoc/ |

Обе страницы документации работают полностью локально: JS-бандлы Swagger UI и Redoc отдаются из пакета `drf-spectacular-sidecar` (версия зафиксирована в `uv.lock`), внешние CDN и шрифты не используются. Redoc подключается классическим `<script>` — бандл в sidecar является UMD-сборкой, поэтому ошибки `Cannot use 'import.meta' outside a module` не возникает.

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

## 12. Правила доступа

| Субъект | Может |
|---|---|
| Любой аутентифицированный пользователь | создать задачу (`created_by` задаётся сервером), видеть только свои задачи и назначенные ему |
| Создатель задачи | читать, менять `title`, `description`, `assigned_to`, `is_completed`, удалять задачу, управлять комментариями как автор |
| Исполнитель | читать задачу и её комментарии, добавлять комментарии, менять **только** `is_completed` |
| Участник (создатель/исполнитель) | просматривать и добавлять комментарии |
| Автор комментария | редактировать и удалять свой комментарий, пока остаётся участником задачи |
| Посторонний | ничего: задача отсутствует в списке и отдаёт `404` по detail и по вложенным комментариям |

После переназначения прежний исполнитель теряет доступ (если не является создателем). Объекты вне доступного queryset → `404`, запрещённая операция внутри набора → `403`. Правила реализованы на сервере в `apps/tasks/services.py` + `apps/tasks/selectors.py`; скрытие кнопок в UI — только UX.

## 13. Структура проекта

```text
.
├── AGENTS.md, spec/            # исходные документы требований
├── config/                     # settings, urls, wsgi/asgi, пагинация, обработчик ошибок
├── apps/
│   ├── users/
│   │   ├── services.py         # регистрация пользователя
│   │   ├── selectors.py        # справочник активных пользователей
│   │   ├── api/                # serializers, views, urls (register/token/me/users)
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
├── templates/                  # base, dashboard, login, register, task_detail,
│                               # drf_spectacular/redoc.html (локальный шаблон Redoc)
├── static/css/styles.css       # дизайн-токены и компоненты, light/dark
├── static/js/                  # theme.js, ui.js, api.js, pages/* (vanilla JS)
├── tests/e2e/                  # браузерные Playwright-тесты (conftest + 5 модулей)
├── docs/ARCHITECTURE.md        # описание реализованной архитектуры
├── docker/entrypoint.sh        # migrate → seed → runserver
├── Dockerfile                  # образ приложения
├── Dockerfile.e2e              # образ тестов на официальном Playwright-образе
├── compose.yaml                # сервис web (+ healthcheck) и профиль e2e
├── .github/workflows/ci.yml    # unit-тесты, линтер и E2E при push/PR
├── .dockerignore, .env.example, .gitignore
├── pyproject.toml, uv.lock, .python-version
└── README.md
```

Направление зависимостей: `web views → templates`, `API views → serializers/selectors/services → models`; модели ничего не импортируют из API, сервисы не знают о HTTP/DRF, selectors не формируют ответы.

## 14. Конфигурация и безопасность

| Переменная | Назначение | Значение по умолчанию |
|---|---|---|
| `APP_PORT` | host-порт приложения в Compose (`${APP_PORT:-8000}:8000`) | `8000` |
| `DJANGO_DEBUG` | режим отладки; `false` блокирует seed и требует настоящего ключа | `true` |
| `DJANGO_SECRET_KEY` | секретный ключ Django | небезопасный dev-ключ (допустимо только при `DEBUG=true`) |
| `DJANGO_ALLOWED_HOSTS` | список хостов через запятую | `localhost,127.0.0.1` (в Compose дополнительно `0.0.0.0,web` — имя сервиса в Compose-сети, без него E2E получает `400 DisallowedHost`) |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | доверенные origin'ы для CSRF | пусто |
| `DJANGO_DB_PATH` | путь к SQLite-файлу | `./data/db.sqlite3` (в Compose: `/app/data/db.sqlite3`) |
| `SEED_DEMO_DATA` | `1` — запускать seed из entrypoint | `0` (`1` в `compose.yaml`) |
| `E2E_BASE_URL` | origin приложения для браузерных тестов | `http://127.0.0.1:8000` (`http://web:8000` в Compose) |
| `E2E_READY_TIMEOUT` | ожидание готовности приложения E2E-тестами, сек | `60` |

Безопасность и гигиена:

- `.env` в git не коммитится (см. `.gitignore`); в репозитории только `.env.example` без секретов.
- `.dockerignore` исключает `.git`, `.venv`, кэши, `.env`, локальную БД и артефакты тестов из образа.
- Пароли хранятся только в хеше Django; в API-ответах нет ни паролей, ни хешей, ни stack trace.
- JWT хранится в `sessionStorage` вкладки; при истечении `access` выполняется максимум одна попытка refresh и один повтор запроса, затем состояние очищается и пользователь возвращается на `/login/`. Токены не попадают в URL, HTML и логи.
- Демо-seed заблокирован при `DEBUG=false`; демо-пароли — только для локального окружения.
- Пользовательский текст в DOM вставляется через `textContent`/создание узлов, без `innerHTML`.
- Страницы API-документации не ходят в сеть за бандлами и шрифтами (локальный sidecar).
- В dev-режиме (`DJANGO_DEBUG=true`) не отправляется заголовок `Cross-Origin-Opener-Policy`: браузеры применяют его только на доверенных origin'ах (`https://` или `localhost`), а локальный Compose отдаёт приложение по `http://web:8000`, где Chromium игнорирует заголовок и пишет ошибку в консоль (ею падают E2E-проверки чистоты консоли). При `DJANGO_DEBUG=false` COOP отправляется как обычно (`same-origin`).

## 15. Известные ограничения

- SQLite и development server (`runserver`) рассчитаны на локальную разработку и проверку задания, **не для production**.
- Compose-сервис `web` — единственный сервис приложения; сервис `e2e` существует только в профиле `e2e` и нужен исключительно для тестов. Отдельного контейнера БД, Redis, Celery и фронтенд-сервиса нет — по условию они не нужны.
- Поиск `?search=` использует `icontains`; SQLite регистронезависимо обрабатывает только ASCII, поэтому для кириллицы дополнительно перебираются варианты регистра (`lower`/`upper`/`capitalize`/`title`). Полный case-insensitive поиск для всех языков потребовал бы расширения ICU или другой СУБД.
- Email делает необязательным, но задаёт уникальность (case-insensitive) — как требует спецификация.
- Real-time обновления, уведомления, вложения и админ-консоль в UI не реализованы — их нет в задании.
- Для комментариев поддерживается `PATCH`, `PUT` возвращается `405` (допускается спецификацией).
- Браузерные тесты работают с реальной (не тестовой) базой приложения: они создают задачи с уникальными заголовками и удаляют их после себя, но зарегистрированные тестом пользователи (`e2e_*`) остаются до сброса базы (`docker compose down -v`).

## 16. Типичные ошибки и их устранение

| Симптом | Причина | Решение |
|---|---|---|
| `Error: That port is already in use` при старте | порт 8000 занят другим процессом | освободите порт (`docker compose down` или остановите старый `runserver`) либо запустите на другом: `APP_PORT=8001 docker compose up --build` |
| E2E: `Application is not reachable at http://web:8000 ... HTTP Error 400: Bad Request` | в `DJANGO_ALLOWED_HOSTS` нет имени сервиса `web` — Django отклоняет `Host: web:8000` (`DisallowedHost`) | добавьте `web` в `DJANGO_ALLOWED_HOSTS` (в `compose.yaml` уже: `localhost,127.0.0.1,0.0.0.0,web`) и перезапустите `--build` |
| E2E падают с console error `The Cross-Origin-Opener-Policy header has been ignored...` | Django шлёт COOP, а origin `http://web:8000` недоверенный — Chromium игнорирует заголовок и логирует ошибку | в dev COOP отключён (`SECURE_CROSS_ORIGIN_OPENER_POLICY = None if DEBUG` в `config/settings.py`); в production при `DEBUG=false` заголовок остаётся |
| `Application is not reachable at ...` от E2E-тестов | приложение не запущено или ещё поднимается | запустите `docker compose up --build` (для Compose используйте профиль `e2e`) либо увеличьте `E2E_READY_TIMEOUT` |
| `Executable doesn't exist at .../chrome-...` | не установлен браузер Chromium | `uv run playwright install chromium` (в Compose-режиме это уже сделано в `Dockerfile.e2e`) |
| Сборка E2E-образа падает или тесты не стартуют в контейнере | версия Playwright в образе не совпадает с `uv.lock` | тег в `Dockerfile.e2e` должен соответствовать пину `playwright==` в `pyproject.toml`; после обновления зависимости пересоберите образ (`--build`) |
| E2E-падение: `Failed to load resource ... 404` на странице документации | собраны не все static-файлы или старый процесс | перезапустите сервер после изменения шаблонов/настроек (шаблоны Django кэшируются процессом) |
| `/api/redoc/` пуст или показывает ошибку в консоли | использовался CDN-бандл Redoc другой major-версии | в проекте используется локальный sidecar-бандл (`REDOC_DIST="SIDECAR"`); проверьте `drf-spectacular-sidecar` в зависимостях и `templates/drf_spectacular/redoc.html` |
| `manage.py migrate` не может создать файл БД | каталог для SQLite не существует | используйте путь по умолчанию `./data/db.sqlite3` (каталог создаётся автоматически) или задайте существующий `DJANGO_DB_PATH` |
| Seed отказался работать | `DJANGO_DEBUG=false` | демо-данные — только для локальной разработки; включите `DJANGO_DEBUG=true` |
| Тесты видят устаревший UI после правки | development server запущен без перезагрузки | перезапустите `runserver` (запускайте с `--reload` либо без `--noreload`, если меняете Python-код/настройки) |

## 17. Документация

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — реализованная архитектура, слои и потоки данных.
- [`spec/`](spec/) — исходные документы требований (`SPEC.md`, `ARCHITECTURE.md`, `LOCAL_DEVELOPMENT.md`, `FRONTEND.md`, `DOCUMENTATION.md`).
- `AGENTS.md` — инструкции для coding agent.
