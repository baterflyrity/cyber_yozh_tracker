"""Browser workflow: create, inspect, edit, assign, complete, comment, delete."""

import uuid

from conftest import DEMO_USERS
from playwright.sync_api import expect


def test_owner_creates_task_through_the_dialog(page, ui, api, owner_token, assert_clean_browser):
    ui.login(page, *DEMO_USERS["owner"])

    title = f"Задача из UI {uuid.uuid4().hex[:8]}"
    page.get_by_role("button", name="Создать задачу").click()
    dialog = page.locator("#task-dialog")
    expect(dialog).to_be_visible()

    # Client-side validation with an inline message next to the field.
    page.get_by_role("button", name="Сохранить").click()
    field_error = dialog.locator('[data-error-for="title"]')
    expect(field_error).to_be_visible()
    expect(field_error).to_contain_text("Укажите заголовок задачи.")
    expect(dialog).to_be_visible()  # dialog must stay open on validation failure

    page.get_by_label("Заголовок").fill(title)
    page.get_by_label("Описание").fill("Описание задачи, созданной в браузере.")
    page.get_by_label("Исполнитель").select_option(label=DEMO_USERS["worker"][0])
    page.get_by_role("button", name="Сохранить").click()

    expect(dialog).to_be_hidden()
    expect(ui.toast(page)).to_have_text("Задача создана")
    card = page.locator(".task-card", has_text=title)
    expect(card).to_be_visible()
    expect(card.locator(".badge")).to_have_text("Не выполнена")
    expect(card).to_contain_text(f"Исполнитель: {DEMO_USERS['worker'][0]}")

    # Server state: creator is the signed-in user, assignment is applied.
    response = api.request("GET", "/api/tasks/?search=" + title, token=owner_token)
    results = response.json()["results"]
    assert len(results) == 1
    task = results[0]
    assert task["created_by"]["username"] == DEMO_USERS["owner"][0]
    assert task["assigned_to"]["username"] == DEMO_USERS["worker"][0]

    # The suite runs against the real application database, so remove the task
    # created through the UI to keep repeated runs free of leftovers.
    deleted = api.request("DELETE", f"/api/tasks/{task['id']}/", token=owner_token)
    assert deleted.status == 204, deleted.text()

    assert_clean_browser()


def test_owner_edits_assigns_completes_comments_and_deletes(
    page, ui, api, owner_token, task_factory, assert_clean_browser
):
    ui.login(page, *DEMO_USERS["owner"])
    task = task_factory(title=f"Полный цикл {uuid.uuid4().hex[:8]}")
    ui.open_task(page, task["id"])

    expect(page.locator("#detail-title")).to_have_text(task["title"])
    expect(page.locator("#detail-author")).to_have_text(DEMO_USERS["owner"][0])
    expect(page.locator("#detail-assignee")).to_have_text("не назначен")
    expect(page.locator("#detail-status-badge")).to_have_text("Не выполнена")

    # --- edit description (creator is allowed) -------------------------------
    page.get_by_role("button", name="Редактировать").click()
    edit_dialog = page.locator("#edit-dialog")
    expect(edit_dialog).to_be_visible()
    page.get_by_label("Описание").fill("Описание обновлено через интерфейс.")
    page.get_by_role("button", name="Сохранить", exact=True).click()
    expect(edit_dialog).to_be_hidden()
    expect(page.locator("#detail-description")).to_have_text("Описание обновлено через интерфейс.")

    # --- assign to the worker ------------------------------------------------
    assignee = page.get_by_label("Исполнитель")
    assignee.select_option(label=DEMO_USERS["worker"][0])
    page.get_by_role("button", name="Сохранить назначение").click()
    expect(page.locator("#detail-assignee")).to_have_text(DEMO_USERS["worker"][0])

    # --- complete and reopen -------------------------------------------------
    page.get_by_role("button", name="Отметить выполненной").click()
    expect(page.locator("#detail-status-badge")).to_have_text("Выполнена")
    expect(page.get_by_role("button", name="Снять отметку о выполнении")).to_be_visible()

    page.get_by_role("button", name="Снять отметку о выполнении").click()
    expect(page.locator("#detail-status-badge")).to_have_text("Не выполнена")

    # --- comments ------------------------------------------------------------
    comment_text = "Комментарий из браузерного теста"
    page.get_by_label("Новый комментарий").fill(comment_text)
    page.get_by_role("button", name="Добавить").click()

    comment = page.locator(".comment", has_text=comment_text)
    expect(comment).to_be_visible()
    expect(comment.locator(".comment-author")).to_have_text(DEMO_USERS["owner"][0])

    # Author may edit their own comment inline. After the click the body moves
    # into the textarea, so the editor is addressed through the list container.
    comment.get_by_role("button", name="Изменить").click()
    updated_text = comment_text + " (изменён)"
    editor = page.locator("#comment-list textarea")
    expect(editor).to_be_visible()
    editor.fill(updated_text)
    page.locator("#comment-list").get_by_role("button", name="Сохранить").click()
    expect(page.locator(".comment-body", has_text=updated_text)).to_be_visible()

    # Server really stored the comment under the right task.
    comments = api.request(
        "GET", f"/api/tasks/{task['id']}/comments/", token=owner_token
    ).json()["results"]
    assert any(item["body"] == updated_text for item in comments)

    # --- delete with confirmation -------------------------------------------
    actions = page.get_by_role("region", name="Действия с задачей")
    actions.get_by_role("button", name="Удалить", exact=True).click()
    confirm = page.locator("#confirm-dialog")
    expect(confirm).to_be_visible()
    expect(page.locator("#confirm-text")).to_contain_text("Удалить задачу")
    confirm.get_by_role("button", name="Удалить").click()

    expect(page).to_have_url(ui.url("/"), timeout=15_000)
    page.get_by_label("Поиск").fill(task["title"])
    expect(page.locator("#empty-state")).to_be_visible()

    # The task is really gone on the server side (task_factory delete is a no-op).
    assert api.request("GET", f"/api/tasks/{task['id']}/", token=owner_token).status == 404

    assert_clean_browser()


def test_empty_comment_is_rejected_with_visible_message(
    page, ui, task_factory, assert_clean_browser
):
    ui.login(page, *DEMO_USERS["owner"])
    task = task_factory(title=f"Комментарии {uuid.uuid4().hex[:8]}")
    ui.open_task(page, task["id"])

    page.get_by_role("button", name="Добавить").click()
    error = page.locator("#comment-error")
    expect(error).to_be_visible()
    expect(error).to_contain_text("Введите текст комментария.")
    expect(page.locator(".comment")).to_have_count(0)

    assert_clean_browser()


def test_task_is_searchable_and_filterable_in_the_list(
    page, ui, api, owner_token, task_factory, assert_clean_browser
):
    ui.login(page, *DEMO_USERS["owner"])
    unique = uuid.uuid4().hex[:8]
    open_title = f"Фильтр открыта {unique}"
    done_title = f"Фильтр выполнена {unique}"
    task_factory(title=open_title)
    done_task = task_factory(title=done_title)
    api.request(
        "PATCH", f"/api/tasks/{done_task['id']}/", token=owner_token, body={"is_completed": True}
    )

    page.goto(ui.url("/"))

    # Search by a unique prefix narrows the list down to both tasks.
    page.get_by_label("Поиск").fill(unique)
    expect(page.locator(".task-card", has_text=open_title)).to_be_visible()
    expect(page.locator(".task-card", has_text=done_title)).to_be_visible()

    # Status filter shows only matching tasks.
    page.get_by_label("Статус").select_option("true")
    expect(page.locator(".task-card", has_text=done_title)).to_be_visible()
    expect(page.locator(".task-card", has_text=open_title)).to_have_count(0)

    page.get_by_label("Статус").select_option("false")
    expect(page.locator(".task-card", has_text=open_title)).to_be_visible()
    expect(page.locator(".task-card", has_text=done_title)).to_have_count(0)

    # Unknown search term gives the empty state with a readable message.
    page.get_by_label("Поиск").fill(f"нетакой-{unique}")
    page.get_by_label("Статус").select_option("")
    expect(page.locator("#empty-state")).to_contain_text("Ничего не найдено")

    assert_clean_browser()
