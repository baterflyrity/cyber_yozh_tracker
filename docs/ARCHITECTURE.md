# Архитектура реализации

Документ описывает **фактически реализованный** код проекта: слои, направление зависимостей и потоки данных. Исходные требования находятся в [`spec/`](../spec/).

## 1. Слои и их ответственность

```text
Браузер (Django templates + vanilla JS)          Клиенты API (curl, Swagger)
        │ fetch /api/…                                  │ Authorization: Bearer
        └───────────────────┬───────────────────────────┘
                            ▼
                 config/urls.py  →  api/ (DRF views)
                            │
        ┌───────────────────┼───────────────────────┐
        ▼                   ▼                       ▼
  api/serializers     api/permissions         selectors.py  ── чтение/выборка
  (транспортная       (грубый уровень        services.py    ── запись и правила
   валидация)          доступа)                    │
        │                   │                      ▼
        └───────────────────┴──────────────►  models.py (Task, Comment)
```

### Models / persistence — `apps/tasks/models.py`

- `Task`: `title` (1–200), `description`, `created_by`, `assigned_to` (nullable), `is_completed`, `created_at`, `updated_at`, индексы по `(created_by, updated_at)` и `(assigned_to, updated_at)`.
- `Comment`: `task` (CASCADE — комментарии удаляются вместе с задачей), `author`, `body` (1–5000), `created_at`, `updated_at`.
- Модели не знают о `request`, DRF и HTTP; содержат только поля, связи, ограничения и значения по умолчанию.

### Domain services — `apps/tasks/services.py`

Единственное место, где меняется состояние и проверяется допустимость:

| Функция | Правило |
|---|---|
| `create_task` | `created_by` всегда = `actor`; назначение только на существующего активного пользователя (`resolve_assignee`) |
| `update_task` | участник → изменения только из разрешённого набора полей; исполнителю разрешён исключительно `is_completed`; постороннему — отказ |
| `delete_task` | только создатель |
| `add_comment` | только участник задачи |
| `update_comment` / `delete_comment` | только автор **и** только пока остаётся участником задачи |
| `is_participant` / `is_creator` | общие policy-проверки, переиспользуемые permissions-классами API |

Сервисы принимают обычные аргументы (`actor`, объект, валидированные данные), не импортируют DRF/HTTP и кидают Django-исключения `PermissionDenied` (→ 403) и `ValidationError` (→ 400). Атомарные операции обёрнуты в `transaction.atomic`.

### Selectors — `apps/tasks/selectors.py`, `apps/users/selectors.py`

- `tasks_visible_to(user)` — единственный источник видимости: `created_by=user OR assigned_to=user`; для анонимного пользователя — пустой набор. Список и detail используют именно его, поэтому чужой объект гарантированно даёт 404.
- `filter_tasks(...)` — `search` (заголовок + описание), `is_completed`, `ordering`.
- `comments_for_task(task)` — комментарии уже проверенной задачи.
- `active_users(search)` — справочник назначения (только активные пользователи).

### API / transport — `apps/*/api/`

- `serializers.py` — транспортная валидация и представление: `UserRefField` принимает `id`, а отдаёт `{id, username}`; `created_by`, `author`, `task` только для чтения; поля задачи/комментария валидируются на длину.
- `permissions.py` — `IsTaskParticipant`, `IsCommentParticipant` вызывают те же policy-функции, что и сервисы (защита в глубину: view сужает queryset, service решает, что можно делать).
- `views.py` — только «HTTP → selector/service → HTTP»: `TaskViewSet` (список с фильтрами/сортировкой/пагинацией, create/update/destroy через сервисы), `CommentViewSet` (вложенные маршруты, `PUT` отключён → 405).
- `urls.py` — роутер DRF: `/api/tasks/` и `/api/tasks/(?P<task_pk>\d+)/comments/`.

`config/exceptions.py` преобразует доменные исключения в стабильные ответы DRF, `config/pagination.py` задаёт страницу по 20 элементов.

### Presentation — `web/`, `templates/`, `static/`

- `web/views.py` — только `TemplateView`: рендерит HTML-shell, не содержит бизнес-логики и не выводит данные без проверки доступа.
- `static/js/api.js` — JWT в `sessionStorage`, одна попытка refresh и один повтор запроса, обработка сетевых ошибок и 401/403/404.
- `static/js/pages/*` — список/создание задач, детали/редактирование/комментарии, вход/регистрация; весь ввод в DOM идёт через `textContent`/`createElement`.
- `static/js/theme.js` — режимы Системная/Светлая/Тёмная, `localStorage`, слушатель `prefers-color-scheme`; инлайн-скрипт в `<head>` применяет сохранённый режим до первой отрисовки.
- `static/css/styles.css` — палитра на CSS custom properties для обеих тем, адаптивные брейкпоинты, `prefers-reduced-motion`.

## 2. Направление зависимостей

```text
web views       → templates/static shell (без обращений к моделям)
API views       → serializers / selectors / services → models
serializers     → models (поля и валидация), не вызывают сервисы
services        → models, django.core.exceptions (не DRF)
selectors       → models (только чтение, без HTTP)
models          → ничего из слоёв выше
```

## 3. Основные потоки

**Создание задачи:** `POST /api/tasks/` → `IsAuthenticated` → `TaskSerializer.is_valid` (длина заголовка, `assigned_to` ∈ активные пользователи) → `services.create_task(actor=request.user, …)` → `201` с сериализованным объектом.

**Запрещённое действие:** view берёт объект из queryset, ограниченного `tasks_visible_to` → посторонний получает `404`; для участника вызов сервиса бросает `PermissionDenied` → `config/exceptions.py` → `403 {"detail": …}`.

**Комментарии:** каждый запрос сначала резолвит `task_pk` через видимый queryset (404 при чужой задаче), затем фильтрует комментарии по этой задаче — обратиться к комментарию одной задачи через URL другой нельзя.

**Ошибка валидации:** сериализатор → `400 {field: [message]}`; ошибки из сервисов → `400 {"detail": [...]}`.

## 4. Принятые упрощения

- Используется стандартная модель пользователя Django (собственный `CustomUser` не вводился): email необязателен, но уникален (case-insensitive) — как допускает спецификация.
- Фильтрация/сортировка реализованы маленькими функциями в selectors вместо django-filter: параметров немного, зависимости не нужны.
- Нет repository/CQRS/event bus: для MVP избыточно (требование `spec/ARCHITECTURE.md`).
- Admin зарегистрирован как удобство разработчика, в UI не используется.
- Демо-seed — management command со стабильными ключами (`username`, `title` + `created_by`), а не фикстуры, чтобы повторный запуск не дублировал данные.
