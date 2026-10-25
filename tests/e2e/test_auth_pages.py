"""Browser flows: pages, login, logout, registration errors."""

import uuid

from conftest import DEMO_USERS, SEED_TASK_TITLE
from playwright.sync_api import expect


def test_home_page_offers_login_for_anonymous(page, ui, assert_clean_browser):
    """Anonymous visitor sees no protected data and a clear call to action."""
    page.goto(ui.url("/"))

    expect(page.get_by_role("heading", name="Задачи")).to_be_visible()
    expect(page.get_by_role("banner").get_by_role("link", name="Войти")).to_be_visible()
    expect(page.get_by_role("button", name="Выйти")).to_be_hidden()
    # No task cards are rendered without authentication.
    expect(page.locator(".task-card")).to_have_count(0)
    expect(page.locator("#empty-state")).to_contain_text("Войдите, чтобы увидеть задачи")
    # Anonymous visitor does not get the filtering controls either.
    expect(page.locator("#filters")).to_be_hidden()
    expect(page.get_by_role("button", name="Создать задачу")).to_be_hidden()

    assert_clean_browser()


def test_login_page_shows_error_for_wrong_credentials(page, ui, assert_clean_browser):
    page.goto(ui.url("/login/"))
    page.get_by_label("Имя пользователя").fill(DEMO_USERS["owner"][0])
    page.get_by_label("Пароль").fill("definitely-wrong-password")
    page.get_by_role("button", name="Войти").click()

    error = page.locator("#login-error")
    expect(error).to_be_visible()
    expect(error).to_contain_text("Неверное имя пользователя или пароль.")
    expect(page).to_have_url(ui.url("/login/"))

    # The 401 response is deliberately provoked by the wrong password.
    assert_clean_browser(allow_http_statuses=(401,))


def test_login_page_requires_username_and_password(page, ui, assert_clean_browser):
    page.goto(ui.url("/login/"))
    page.get_by_label("Имя пользователя").fill(DEMO_USERS["owner"][0])
    page.get_by_role("button", name="Войти").click()

    error = page.locator("#login-error")
    expect(error).to_be_visible()
    expect(error).to_contain_text("Укажите имя пользователя и пароль.")
    expect(page).to_have_url(ui.url("/login/"))

    assert_clean_browser()


def test_login_shows_seeded_tasks_and_logout_clears_state(page, ui, assert_clean_browser):
    ui.login(page, *DEMO_USERS["owner"])

    expect(page.get_by_role("heading", name="Задачи")).to_be_visible()
    expect(page.locator("#current-user")).to_have_text(DEMO_USERS["owner"][0])

    # Seeded demo task must be findable for its author (search filters the list).
    page.get_by_label("Поиск").fill(SEED_TASK_TITLE[:20])
    expect(page.locator(".task-card h2 a", has_text=SEED_TASK_TITLE)).to_be_visible()

    ui.logout(page)

    # Session state is cleared: the workspace no longer shows protected data.
    page.goto(ui.url("/"))
    expect(page.get_by_role("banner").get_by_role("link", name="Войти")).to_be_visible()
    expect(page.locator(".task-card")).to_have_count(0)

    assert_clean_browser()


def test_register_form_validates_and_creates_account(page, ui, assert_clean_browser):
    page.goto(ui.url("/register/"))

    # Empty submit keeps the user on the page with an inline message.
    page.get_by_role("button", name="Зарегистрироваться").click()
    username_error = page.locator('[data-error-for="username"]')
    expect(username_error).to_be_visible()
    expect(username_error).to_contain_text("Укажите имя пользователя.")

    # Server-side validation of a weak password is rendered next to the field.
    username = f"e2e_{uuid.uuid4().hex[:8]}"
    page.get_by_label("Имя пользователя").fill(username)
    page.get_by_label("Пароль", exact=True).fill("12345678")
    page.get_by_role("button", name="Зарегистрироваться").click()
    password_error = page.locator('[data-error-for="password"]')
    expect(password_error).to_be_visible()

    # A valid registration signs the user in and opens the workspace.
    page.get_by_label("Пароль", exact=True).fill("E2e-Str0ng-Pass!")
    page.get_by_role("button", name="Зарегистрироваться").click()

    expect(page).to_have_url(ui.url("/"), timeout=15_000)
    expect(page.locator("#current-user")).to_have_text(username)

    # The 400 response is deliberately provoked by the weak password attempt.
    assert_clean_browser(allow_http_statuses=(400,))

