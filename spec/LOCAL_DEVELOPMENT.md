# Локальный запуск, Docker Compose и E2E-данные

Этот документ определяет воспроизводимый локальный запуск приложения и актуальный способ выполнять автоматические браузерные тесты. Он дополняет `SPEC.md`, `FRONTEND.md` и `DOCUMENTATION.md`.

## 1. Репозиторий и агентское окружение

- Репозиторий приложения: `https://github.com/baterflyrity/cyber_yozh_tracker`.
- В текущем агентском окружении исходный код приложения находится в `/app/cyber_yozh_tracker`.
- Это рабочая директория внутри отдельного окружения `dockerusp`. В ней доступны Docker и Docker Compose, а порты 8000–8010 предоставлены для локальных сервисов. Перед использованием проверить фактическую доступность команд, демона и портов.
- Внешний контейнер не обязан иметь установленный GUI-браузер. Автоматизированные E2E-тесты должны запускать headless Chromium внутри специального Compose-сервиса `e2e`, основанного на официальном образе Playwright.
- Не менять Dockerfile или настройки самого `dockerusp`, не запускать второй Docker daemon поверх доступного демона и не требовать привилегированного режима для контейнеров приложения.

Первые проверки в рабочей директории:

```bash
pwd
git rev-parse --show-toplevel
git status --short --branch
docker version
docker compose version
docker info
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

Если команда Docker не может связаться с daemon, сначала зафиксировать её полный вывод и разобраться с доступом к предоставленному daemon. Не заменять проверку Docker запросами `curl` и не изменять окружение-хост без необходимости.

## 2. Архитектура Compose

Локальный стек использует Django и SQLite. Отдельный контейнер PostgreSQL не нужен. Минимально необходимы:

- `web` — Django-приложение, миграции, локальный seed и сервер;
- `e2e` — отдельный тестовый контейнер с Python, pytest, Playwright и Chromium; запускается профилем `e2e`;
- именованный volume для SQLite;
- каталог `test-results/` для диагностических файлов браузерных тестов.

`compose.yaml` должен удовлетворять требованиям:

1. `web` слушает `0.0.0.0:8000` внутри контейнера.
2. Host-порт настраивается переменной `APP_PORT`, по умолчанию 8000: `"${APP_PORT:-8000}:8000"`.
3. Не задавать фиксированный `container_name`: это мешает изолированным запускам с разными Compose project names.
4. SQLite хранится в именованном volume, а не в файловом слое контейнера.
5. Healthcheck `web` должен проверять реальную готовность приложения после миграций и seed, например доступность `/api/schema/`.
6. `e2e` зависит от `web` с `condition: service_healthy`.
7. Из `e2e` приложение вызывается через `E2E_BASE_URL=http://web:8000`. Не использовать `localhost` для межконтейнерного соединения: внутри `e2e` это сам тестовый контейнер.
8. E2E-образ и Python-пакет `playwright` должны использовать совместимые, зафиксированные версии. Проверить согласованность `Dockerfile.e2e`, `pyproject.toml` и `uv.lock`.
9. Тестовый контейнер должен завершаться ненулевым кодом при падении pytest; Compose-команда обязана возвращать этот код.
10. Временные каталоги и bind mounts должны быть созданы до теста и доступны для записи. Не включать screenshots, videos, traces, `.env`, секреты и SQLite-файлы в Git.

## 3. Старт приложения

Перед первым запуском проверить Compose-конфигурацию:

```bash
docker compose config --quiet
```

Обычный запуск приложения:

```bash
docker compose up --build -d
docker compose ps
docker compose logs --tail=200 web
```

Если host-порт 8000 занят, использовать свободный порт из доступного диапазона, например:

```bash
APP_PORT=8001 docker compose up --build -d
```

Адреса при порте по умолчанию:

- UI: `http://127.0.0.1:8000/`
- Swagger UI: `http://127.0.0.1:8000/api/docs/`
- Redoc: `http://127.0.0.1:8000/api/redoc/`
- OpenAPI schema: `http://127.0.0.1:8000/api/schema/`

При `APP_PORT=8001` поменять host URL на порт 8001. Внутренний адрес `http://web:8000` для E2E от host-порта не зависит.

Проверить, что приложение готово:

```bash
docker compose ps
curl --fail --show-error http://127.0.0.1:${APP_PORT:-8000}/api/schema/ -o /dev/null
```

В логах должны быть успешные миграции, сообщение о seed (если `SEED_DEMO_DATA=1`) и запуск сервера. Если `web` не становится `healthy`, сначала диагностировать его логи и healthcheck — не запускать E2E в состоянии, когда приложение не готово.

## 4. Демонстрационные данные

В локальной Compose-конфигурации `SEED_DEMO_DATA=1` включает Django-команду `seed_demo_data`. Она должна быть идемпотентной: повторный запуск не создаёт дубликаты и не изменяет пароль уже существующего пользователя. Команда не должна автоматически включаться в production.

| Username | Пароль | Назначение |
|---|---|---|
| `demo_owner` | `DemoOwner123!` | Создатель задачи |
| `demo_worker` | `DemoWorker123!` | Исполнитель, может менять статус |
| `demo_outsider` | `DemoOutsider123!` | Проверка запрета доступа |

Пароли предназначены только для локальной разработки и проверки. Они не должны использоваться в production. Seed создаёт стабильные демонстрационные задачи и комментарии, описанные в README.

## 5. Запуск браузерных E2E через Compose

**Это предпочтительный способ в агентском окружении.** Не требуется устанавливать браузер в `/app/cyber_yozh_tracker` или в контейнер `dockerusp`: Chromium поставляется образом Playwright для сервиса `e2e`.

Из корня `/app/cyber_yozh_tracker` сначала проверь конфигурацию и подготовь каталог артефактов:

```bash
pwd
docker compose --profile e2e config --quiet
mkdir -p test-results
```

Для изолированного прогона использовать выделенное имя проекта и свободный опубликованный host-порт. Пример ниже предполагает, что проект `cyberyozh-e2e` зарезервирован только для тестов:

```bash
# Очистить только предыдущий тестовый Compose-проект и его volume.
# Не выполняй эту команду с именем обычного пользовательского проекта.
docker compose -p cyberyozh-e2e --profile e2e down -v --remove-orphans

# Собрать web и Playwright-образ, поднять web, дождаться healthcheck,
# затем запустить реальный headless Chromium и pytest.
APP_PORT=8001 docker compose -p cyberyozh-e2e --profile e2e up \
  --build --abort-on-container-exit --exit-code-from e2e
```

`--exit-code-from e2e` должен передать итоговый код сервиса `e2e`; падение тестов не должно превращаться в успешный exit code. Сервис `e2e` обращается к `http://web:8000` по внутренней сети Compose. Внешний порт 8001 нужен только для диагностики UI снаружи и не меняет внутренний адрес тестов.

Для повторяемости прогона использовать изолированный проект либо очистить только выделенный test volume. Не удалять volume основного приложения без явной необходимости. После сохранения логов тестовый стек можно остановить и удалить:

```bash
docker compose -p cyberyozh-e2e --profile e2e logs --no-color

docker compose -p cyberyozh-e2e --profile e2e down -v --remove-orphans
```

Если команда упала, прежде чем очищать контейнеры, сохрани stdout/stderr, `docker compose ... ps -a`, `docker compose ... logs --no-color web e2e` и файлы из `test-results/`. Помни: pytest-playwright удаляет весь `test-results/` в начале каждого следующего прогона, поэтому артефакты забираем сразу после падения, а сессионные логи (воспроизведение сбоя, полный вывод pytest) складываем в `logs/` (каталог в `.gitignore`).

## 6. Как диагностировать сбой Compose E2E

Разделяй причины по этапу, на котором возник сбой:

1. **Compose config** — синтаксис YAML, несуществующая переменная, неверный путь к Dockerfile или неразрешённая ссылка сервиса.
2. **Build** — ошибка pull/build, несовпадение версии Playwright и Chromium, `uv sync --frozen`, отсутствующий lock-файл или зависимость.
3. **web не healthy** — логи Django, миграции, SQLite volume, seed, `ALLOWED_HOSTS`, healthcheck и реальный HTTP-ответ `/api/schema/`.
4. **e2e не стартует** — `depends_on`, DNS-имя `web`, права записи `test-results`, команда pytest, установленные плагины и Python-зависимости.
5. **pytest стартует, но тесты падают** — первая ошибка/traceback, browser trace, screenshot и console/network errors; это уже ошибка приложения или тестового сценария, а не проблема старта Compose.
6. **Docker daemon / порты** — вывод `docker info`, `docker ps`, проверка занятого host-порта. Для тестового запуска выбрать другой `APP_PORT` в диапазоне 8000–8010.

Не скрывать исключения, не менять `depends_on` на `sleep`, не убирать healthcheck и не заменять Playwright на `curl`. Проверка `curl` может использоваться как дополнительная диагностика готовности, но не вместо браузерных тестов.

Подтверждённые в этой сессии сбои и их решения (проверены логами, см. `spec/COMPOSE_E2E_RECOVERY.md`):

- `E2E: Application is not reachable at http://web:8000 ... HTTP Error 400` + `DisallowedHost: Invalid HTTP_HOST header: 'web:8000'` в логах `web` — в `DJANGO_ALLOWED_HOSTS` нет имени сервиса `web`; healthcheck при этом проходит, потому что ходит на `127.0.0.1`.
- console error `The Cross-Origin-Opener-Policy header has been ignored...` в assertions `assert_clean_browser` — Django шлёт COOP на недоверенном origin `http://web:8000`; в dev COOP отключён в `config/settings.py` (`SECURE_CROSS_ORIGIN_OPENER_POLICY = None if DEBUG`).
- `Error: That port is already in use` или конфликт имён контейнеров при параллельном запуске — используйте `APP_PORT` и изолированное имя проекта (`-p cyberyozh-e2e`); фиксированных `container_name` в `compose.yaml` нет.

## 7. Unit/integration-тесты и линтер

Использовать реальные команды проекта, проверив наличие зависимостей в образе:

```bash
# В обычном окружении, где установлен uv:
uv sync --frozen
uv run pytest
uv run ruff check .
uv run python manage.py makemigrations --check --dry-run
```

Для E2E использовать исключительно подтверждённую команду сервиса `e2e` или эквивалентный запуск с тем же официальным Playwright-образом и установленными зависимостями. Не предполагать, что пакет pytest-playwright или Chromium доступны в контейнере `web`, пока это не проверено.

## 8. Очистка и безопасность

```bash
# Остановить стандартный стек, сохранить данные

docker compose down

# Полный сброс стандартной локальной базы — удаляет SQLite volume
# и все созданные в нём локальные данные
docker compose down -v
```

Для временного прогона с `-p cyberyozh-e2e` очищать только ресурсы этого имени проекта. Не использовать `docker system prune`, не удалять все volumes и не выполнять глобальную очистку Docker daemon в ходе диагностики.
