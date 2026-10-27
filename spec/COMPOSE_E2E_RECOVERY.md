# Спецификация: восстановление Docker Compose и Playwright E2E

## Контекст задачи

Текущий код приложения находится в репозитории `https://github.com/baterflyrity/cyber_yozh_tracker`. Агент работает в новом окружении, без истории предыдущей сессии, из каталога `/app/cyber_yozh_tracker`. Окружение предоставляет Docker, Docker Compose и диапазон публикуемых портов 8000–8010. Эти предпосылки нужно подтвердить, а не считать бесспорными: `pwd`, `git rev-parse --show-toplevel`, `docker version`, `docker compose version`, `docker info`.

Старый агент сообщал, что браузерные тесты в Compose не запускаются. На момент текущей сессии сбой воспроизведён и первопричины подтверждены логами (см. «Подтверждённые первопричины» ниже); исходный вывод сохранён в `logs/repro-disallowedhost.log` (все логи сессии — в `logs/`, каталог в `.gitignore`; держать их в `test-results/` нельзя — pytest-playwright удаляет этот каталог в начале каждого прогона). Нельзя заранее утверждать о новой проблеме в Playwright, Docker, зависимостях или healthcheck: сначала воспроизвести сбой и сохранить полный вывод.

## Подтверждённые первопричины (текущая сессия)

1. **`DisallowedHost` (этап: тесты).** `compose.yaml` задавал `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0` без имени сервиса `web`. Healthcheck `web` ходит на `127.0.0.1` и проходил, а запросы `e2e` на `http://web:8000` отклонялись с `400 Bad Request` (`django.core.exceptions.DisallowedHost: Invalid HTTP_HOST header: 'web:8000'`). Все 22 теста падали в фикстуре `app_ready` с `RuntimeError: Application is not reachable ... HTTP Error 400` (exit code 1). Исправление: `web` добавлен в `DJANGO_ALLOWED_HOSTS`.
2. **Игнорируемый `Cross-Origin-Opener-Policy` (этап: assertions).** После исправления Host'а 14 из 22 тестов падали на `assert_clean_browser` с console error Chromium: «The Cross-Origin-Opener-Policy header has been ignored...» — Django `SecurityMiddleware` по умолчанию шлёт COOP, но origin `http://web:8000` недоверенный, и Chromium игнорирует заголовок, логируя ошибку. Исправление: `SECURE_CROSS_ORIGIN_OPENER_POLICY = None` при `DEBUG=true` в `config/settings.py` (в production заголовок остаётся). Тесты не ослаблялись.
3. **Фиксированные `container_name` и порт.** Убран `container_name: cyberyozh-web`, порт сделан `${APP_PORT:-8000}:8000` — иначе изолированный `-p cyberyozh-e2e` конфликтует с обычным запуском.

## Обязательный подход

- Сохранить существующую реализацию Django, REST API, UI, права доступа и бизнес-правила.
- Не переписывать приложение с нуля.
- Не устанавливать GUI-браузер во внешний агентский контейнер как обязательное условие.
- Запускать browser E2E через `e2e` Compose-профиль и официальный Playwright Python image с headless Chromium.
- Не заменять реальные браузерные тесты запросами `curl`, Django test client или моками.
- Сохранять несовпадающие версии библиотек и browser revision согласованными между `pyproject.toml`, `uv.lock` и `Dockerfile.e2e`.
- Не подавлять ошибки, не добавлять бессмысленные ожидания `sleep`, не снимать assertions и не помечать тесты skip только ради зелёного результата.
- Не выполнять разрушительные операции над чужими контейнерами, image-ами или volumes. Использовать выделенное Compose project name для изоляции.

## Обязательный этап A — воспроизведение до правок

Из корня репозитория выполни и сохрани результаты:

```bash
pwd
git rev-parse --show-toplevel
git status --short --branch
docker version
docker compose version
docker info
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
docker compose config --quiet
docker compose --profile e2e config --quiet
```

Изучи `compose.yaml`, `Dockerfile`, `Dockerfile.e2e`, `docker/entrypoint.sh`, `pyproject.toml`, `uv.lock`, `tests/e2e/`, `.github/workflows/ci.yml`, `.dockerignore` и README. Запиши версии Python, Django, `playwright`, pytest-playwright и Playwright image. Проверь фактическую структуру E2E-файлов — не придумывай имена файлов заранее.

Затем воспроизведи текущую команду из README/Compose в отдельном project name. Если конфигурация ещё не поддерживает `APP_PORT`, сначала попробуй порт по умолчанию, затем зафиксируй портовую проблему и только после этого добавь конфигурируемый порт.

Собери лог полной команды, exit code, список сервисов и логи каждого сервиса до очистки. Зафиксируй, на каком этапе возникла ошибка: config, build, readiness, старт тестового контейнера или сами тесты.

## Обязательный этап B — исправить конфигурацию без обходов

Проверь и при необходимости исправь:

1. `compose.yaml` проходит `docker compose config --quiet` и `docker compose --profile e2e config --quiet`.
2. Host-порт задаётся через `APP_PORT` с безопасным default 8000, например `${APP_PORT:-8000}:8000`, чтобы можно было использовать 8001–8010 без изменения исходников.
3. Удалён фиксированный `container_name`, если он препятствует запуску изолированного Compose project name. Compose должен автоматически создавать имена контейнеров, включающие имя проекта.
4. SQLite использует project-scoped named volume. Не подключай существующий пользовательский volume к тестовому проекту.
5. `web` запускает миграции и seed с ненулевым кодом при ошибке, а healthcheck подтверждает реальную готовность приложения.
6. `e2e` выполняется только после `web: service_healthy`.
7. Для E2E используется `E2E_BASE_URL=http://web:8000`. Не заменять его на `localhost`, `127.0.0.1` или published host port.
8. `Dockerfile.e2e` использует официальный Playwright Python image с версией, согласованной с точной версией пакета `playwright` в lock-файле.
9. В E2E-образе доступны `pytest`, `pytest-django`, `pytest-playwright`, Playwright Python API, Chromium и системные зависимости браузера; они не должны устанавливаться вручную на каждое выполнение тестов.
10. Команда сервиса выполняет реальные E2E-файлы, возвращает exit code pytest и оставляет диагностику при падении.
11. Test artifacts пишутся в `test-results/`, если это возможно в окружении. Проверить права записи и не коммитить артефакты.
12. Seed-данные и тесты воспроизводимы. Тесты не должны зависеть от случайных ID, выполнения в конкретном порядке или модифицированного состояния постоянной БД.

Если ошибка оказалась в зависимости, Dockerfile, healthcheck, сетевом имени, ожидании сервера, правах каталога или самих тестах — исправь первопричину в соответствующем месте. Не добавляй sleep для сокрытия гонки: используй `service_healthy` и явную проверку готовности.

## Обязательный этап C — команды проверки

Сначала проверь конфигурацию и сборку:

```bash
docker compose config --quiet
docker compose --profile e2e config --quiet
docker compose --profile e2e build web e2e
```

Создай каталог вывода:

```bash
mkdir -p test-results
```

Используй отдельный project name `cyberyozh-e2e` и порт, доступный в данном окружении. Перед удалением объёмов убедись, что этот project name используется только для временного прогона:

```bash
docker compose -p cyberyozh-e2e --profile e2e down -v --remove-orphans
APP_PORT=8001 docker compose -p cyberyozh-e2e --profile e2e up \
  --build --abort-on-container-exit --exit-code-from e2e
```

Если прогон завершился с ошибкой, до остановки сервисов собери:

```bash
docker compose -p cyberyozh-e2e --profile e2e ps -a
docker compose -p cyberyozh-e2e --profile e2e logs --no-color web e2e
find test-results -maxdepth 4 -type f -print
```

Используй shell wrapper, сохраняющий настоящий exit code `up` при перенаправлении вывода в `tee`. Не теряй exit code из-за pipeline. После сбора данных останови только выделенный проект:

```bash
docker compose -p cyberyozh-e2e --profile e2e down --remove-orphans
```

После исправлений повтори полный прогон. Сделай минимум два последовательных чистых запуска с удалением только test project volume между ними, чтобы подтвердить воспроизводимость и отсутствие зависимости от состояния базы. Успех подтверждается фактическим кодом возврата 0 и summary pytest, а не только статусом HTTP 200 у приложения.

## Обязательный этап D — тестирование

- Отдельно запусти unit/integration tests и Ruff, используя существующий механизм зависимости проекта.
- Убедись, что Playwright запускает настоящий headless Chromium внутри `e2e`. Если нужна дополнительная проверка, выведи версию браузера/Playwright и добавь это в диагностический отчёт.
- Проверь, что браузерные тесты проверяют настоящий UI и ожидаемые пользовательские операции, а не только `page.request` или API.
- Убедись, что проверки не полагаются на ID демо-объектов, жёстко заданные предположения о пустой БД или порядок запуска.
- Падение сценария должно оставлять screenshot/trace и понятную причину, если их запись доступна.
- Проверь `Redoc`, Swagger UI, ключевые JS console errors и failed requests, если эти сценарии уже есть в наборе.
- Проверить, что повторный запуск Compose не создаёт дубликаты demo users/tasks/comments.
- Проверь, что `docker compose down` не удаляет volume, а `down -v` удаляет только нужный локальный проект. Не применять `docker system prune`.

## Обязательный этап E — документация и спецификации

Обнови README и при необходимости `spec/SPEC.md`, `spec/LOCAL_DEVELOPMENT.md` и workflow CI, чтобы:

- команды соответствовали проверенной конфигурации;
- был описан headless E2E внутри Compose;
- были документированы переменная `APP_PORT`, внутренний URL `http://web:8000`, healthcheck/seed и команда проверки;
- были приведены команды просмотра логов, артефактов, очистки тестового project name и запуска тестов;
- не обещались проверки, которые реально не выполнялись;
- удалённые или ошибочные файлы/ссылки не упоминались.

Убедись, что `.github/workflows/ci.yml` использует корректную команду Compose и завершает job с ненулевым кодом, если E2E падает. Не вноси изменения в workflow только ради видимости; проверь его по фактическому Compose-поведению.

## Критерии готовности

Работа считается завершённой только если:

- Docker daemon и Compose были проверены в текущем контейнерном окружении;
- обе Compose-конфигурации валидны;
- образы `web` и `e2e` собраны;
- `web` становится healthy и миграции/seed завершаются успешно;
- headless Chromium действительно стартует в `e2e`-контейнере;
- pytest возвращает 0 дважды подряд на чистом test volume;
- unit/integration тесты и линтер реально запущены и их результаты записаны;
- артефакты и логи доступны при необходимости;
- README и спецификации совпадают с фактическими командами.

Если выполнение всё ещё невозможно, предоставь точную первопричину с командой, полным сообщением ошибки и шагом воспроизведения. Не объявляй работу успешно завершённой и не подменяй отсутствующее выполнение тестов предположениями.
