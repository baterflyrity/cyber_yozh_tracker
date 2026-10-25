"""Access rules checked in the browser **and** against the real API.

Hiding a button is only UX: every forbidden operation is also attempted through
the API and the stored data is verified afterwards.
"""

import uuid

from conftest import DEMO_USERS
from playwright.sync_api import expect


def test_worker_may_toggle_status_but_nothing_else(
    page, ui, api, owner_token, worker_token, task_factory, demo_user_ids, assert_clean_browser
):
    task = task_factory(title=f"Права исполнителя {uuid.uuid4().hex[:8]}",
                        assigned_to=demo_user_ids[DEMO_USERS["worker"][0]])

    ui.login(page, *DEMO_USERS["worker"])
    ui.open_task(page, task["id"])

    # UI: only the status action is offered to the assignee.
    expect(page.get_by_role("button", name="Отметить выполненной")).to_be_visible()
    expect(page.get_by_role("button", name="Редактировать")).to_be_hidden()
    expect(page.get_by_role("button", name="Удалить")).to_be_hidden()
    expect(page.locator("#assign-block")).to_be_hidden()

    # Status change actually works and reaches the server.
    page.get_by_role("button", name="Отметить выполненной").click()
    expect(page.locator("#detail-status-badge")).to_have_text("Выполнена")
    stored = api.request("GET", f"/api/tasks/{task['id']}/", token=worker_token).json()
    assert stored["is_completed"] is True

    # Forbidden operations attempted directly against the API from the browser.
    forbidden_payloads = [
        {"title": "Hacked title"},
        {"description": "Hacked description"},
        {"assigned_to": demo_user_ids[DEMO_USERS["outsider"][0]]},
        {"is_completed": False, "title": "Hacked again"},
    ]
    for payload in forbidden_payloads:
        response = api.request("PATCH", f"/api/tasks/{task['id']}/", token=worker_token, body=payload)
        assert response.status == 403, f"{payload} -> {response.status}"

    delete_response = api.request("DELETE", f"/api/tasks/{task['id']}/", token=worker_token)
    assert delete_response.status == 403

    # Nothing was silently changed: the task still exists with the same fields.
    after = api.request("GET", f"/api/tasks/{task['id']}/", token=owner_token)
    assert after.status == 200
    data = after.json()
    assert data["title"] == task["title"]
    assert data["description"] == "Создана браузерным тестом."
    assert data["assigned_to"]["username"] == DEMO_USERS["worker"][0]

    assert_clean_browser()


def test_outsider_has_no_access_to_a_foreign_task(
    page, ui, api, owner_token, outsider_token, task_factory, assert_clean_browser
):
    task = task_factory(title=f"Чужая задача {uuid.uuid4().hex[:8]}")
    comment_body = "Комментарий владельца"
    created = api.request(
        "POST", f"/api/tasks/{task['id']}/comments/", token=owner_token, body={"body": comment_body}
    )
    assert created.status == 201
    comment_id = created.json()["id"]

    ui.login(page, *DEMO_USERS["outsider"])

    # Browser: direct URL shows a readable "not found / no access" state.
    page.goto(ui.url(f"/tasks/{task['id']}/"))
    expect(page.locator("#task-detail")).to_be_hidden()
    expect(page.locator("#detail-status")).to_contain_text(
        "Задача не найдена или она вам недоступна."
    )

    # Browser: the task does not appear in the list either.
    page.goto(ui.url("/"))
    page.get_by_label("Поиск").fill(task["title"])
    expect(page.locator("#empty-state")).to_be_visible()
    expect(page.locator(".task-card")).to_have_count(0)

    # Server: the API answers consistently for the outsider.
    assert api.request("GET", f"/api/tasks/{task['id']}/", token=outsider_token).status == 404
    assert (
        api.request("GET", f"/api/tasks/{task['id']}/comments/", token=outsider_token).status == 404
    )
    assert (
        api.request(
            "POST",
            f"/api/tasks/{task['id']}/comments/",
            token=outsider_token,
            body={"body": "intrusion"},
        ).status
        == 404
    )
    assert api.request("DELETE", f"/api/tasks/{task['id']}/", token=outsider_token).status == 404

    # The task and its comment are untouched.
    assert api.request("GET", f"/api/tasks/{task['id']}/", token=owner_token).status == 200
    comments = api.request(
        "GET", f"/api/tasks/{task['id']}/comments/", token=owner_token
    ).json()["results"]
    assert [c["body"] for c in comments] == [comment_body]
    assert comments[0]["id"] == comment_id

    # The 404 responses above are deliberately provoked foreign-object probes.
    assert_clean_browser(allow_http_statuses=(404,))


def test_comment_can_be_changed_only_by_its_author(
    page, ui, api, owner_token, worker_token, task_factory, demo_user_ids, assert_clean_browser
):
    task = task_factory(
        title=f"Комментарии прав {uuid.uuid4().hex[:8]}",
        assigned_to=demo_user_ids[DEMO_USERS["worker"][0]],
    )
    body = "Авторский комментарий"
    created = api.request(
        "POST", f"/api/tasks/{task['id']}/comments/", token=owner_token, body={"body": body}
    )
    assert created.status == 201
    comment_id = created.json()["id"]

    ui.login(page, *DEMO_USERS["worker"])
    ui.open_task(page, task["id"])

    # The worker sees the comment (participant) but gets no edit controls.
    comment = page.locator(".comment", has_text=body)
    expect(comment).to_be_visible()
    expect(comment.get_by_role("button", name="Изменить")).to_have_count(0)
    expect(comment.get_by_role("button", name="Удалить")).to_have_count(0)

    # ... and the server refuses the operations too.
    patch = api.request(
        "PATCH",
        f"/api/tasks/{task['id']}/comments/{comment_id}/",
        token=worker_token,
        body={"body": "hijacked"},
    )
    assert patch.status == 403
    remove = api.request(
        "DELETE", f"/api/tasks/{task['id']}/comments/{comment_id}/", token=worker_token
    )
    assert remove.status == 403

    stored = api.request(
        "GET", f"/api/tasks/{task['id']}/comments/", token=owner_token
    ).json()["results"]
    assert stored[0]["body"] == body  # nothing changed

    # A participant still may add a comment through the UI.
    own_comment = "Комментарий исполнителя из UI"
    page.get_by_label("Новый комментарий").fill(own_comment)
    page.get_by_role("button", name="Добавить").click()
    expect(page.locator(".comment", has_text=own_comment)).to_be_visible()

    # The author keeps full control over their own comment.
    updated = api.request(
        "PATCH",
        f"/api/tasks/{task['id']}/comments/{comment_id}/",
        token=owner_token,
        body={"body": body + " (обновлён)"},
    )
    assert updated.status == 200

    assert_clean_browser()


def test_worker_cannot_reassign_task_and_sees_no_assignment_controls(
    page, ui, api, worker_token, owner_token, task_factory, demo_user_ids, assert_clean_browser
):
    task = task_factory(
        title=f"Нельзя переназначить {uuid.uuid4().hex[:8]}",
        assigned_to=demo_user_ids[DEMO_USERS["worker"][0]],
    )

    ui.login(page, *DEMO_USERS["worker"])
    ui.open_task(page, task["id"])
    expect(page.locator("#assign-block")).to_be_hidden()

    response = api.request(
        "PATCH",
        f"/api/tasks/{task['id']}/",
        token=worker_token,
        body={"assigned_to": demo_user_ids[DEMO_USERS["owner"][0]]},
    )
    assert response.status == 403

    data = api.request("GET", f"/api/tasks/{task['id']}/", token=owner_token).json()
    assert data["assigned_to"]["username"] == DEMO_USERS["worker"][0]

    assert_clean_browser()
