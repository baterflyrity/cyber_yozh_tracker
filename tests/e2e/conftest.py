"""Shared fixtures for the browser E2E tests.

The tests always run against a **real running application** (Docker Compose or
a local dev server) with seeded demo data. They never touch a test database.

Configuration via environment variables:

* ``E2E_BASE_URL``      — application origin, default ``http://127.0.0.1:8000``
                          (inside Compose it is set to ``http://web:8000``);
* ``E2E_READY_TIMEOUT`` — seconds to wait for the app, default ``60``.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.request
import uuid

import pytest
from playwright.sync_api import expect

DEMO_USERS = {
    "owner": ("demo_owner", "DemoOwner123!"),
    "worker": ("demo_worker", "DemoWorker123!"),
    "outsider": ("demo_outsider", "DemoOutsider123!"),
}

SEED_TASK_TITLE = "Подготовить демонстрационный API-сценарий"


@pytest.fixture(scope="session")
def base_url() -> str:
    """Origin of the application under test (overrides pytest-playwright)."""
    return os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


@pytest.fixture(scope="session", autouse=True)
def app_ready(base_url: str) -> None:
    """Wait until the app answers; fail fast with an actionable message."""
    timeout = float(os.environ.get("E2E_READY_TIMEOUT", "60"))
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/api/schema/", timeout=5) as response:
                if response.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001 - connectivity probe only
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(
        f"Application is not reachable at {base_url} (waited {timeout:.0f}s): {last_error}. "
        "Start it first: `docker compose up --build` "
        "or `uv run python manage.py runserver`."
    )


@pytest.fixture
def api(page, base_url):
    """JSON API calls executed through the browser's own request context."""

    class Api:
        def request(self, method: str, path: str, token: str | None = None, body=None):
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            return page.request.fetch(
                f"{base_url}{path}",
                method=method,
                headers=headers,
                data=json.dumps(body) if body is not None else None,
            )

        def token(self, username: str, password: str) -> str:
            response = self.request(
                "POST", "/api/auth/token/", body={"username": username, "password": password}
            )
            assert response.status == 200, response.text()
            return response.json()["access"]

        def json(self, method: str, path: str, token: str | None = None, body=None):
            response = self.request(method, path, token=token, body=body)
            return response

    return Api()


@pytest.fixture
def owner_token(api):
    return api.token(*DEMO_USERS["owner"])


@pytest.fixture
def worker_token(api):
    return api.token(*DEMO_USERS["worker"])


@pytest.fixture
def outsider_token(api):
    return api.token(*DEMO_USERS["outsider"])


@pytest.fixture
def demo_user_ids(api, owner_token):
    """Map of demo usernames to ids as seen through the real API."""
    response = api.request("GET", "/api/users/?page_size=100", token=owner_token)
    assert response.status == 200, response.text()
    return {item["username"]: item["id"] for item in response.json()["results"]}


@pytest.fixture
def task_factory(api, owner_token):
    """Create tasks through the API and delete them after the test."""
    created: list[tuple[int, str]] = []

    def factory(token: str | None = None, title: str | None = None, **kwargs):
        actor_token = token or owner_token
        payload = {
            "title": title or f"E2E задача {uuid.uuid4().hex[:8]}",
            "description": kwargs.pop("description", "Создана браузерным тестом."),
            "assigned_to": kwargs.pop("assigned_to", None),
        }
        assert not kwargs, f"unexpected fields: {sorted(kwargs)}"
        response = api.request("POST", "/api/tasks/", token=actor_token, body=payload)
        assert response.status == 201, response.text()
        data = response.json()
        created.append((data["id"], actor_token))
        return data

    yield factory

    for task_id, token in created:
        api.request("DELETE", f"/api/tasks/{task_id}/", token=token)


@pytest.fixture
def ui(base_url):
    """Common browser interactions using accessible roles and labels."""

    class UI:
        url = staticmethod(lambda path="": f"{base_url}{path}")

        @staticmethod
        def login(page, username: str, password: str) -> None:
            page.goto(f"{base_url}/login/")
            page.get_by_label("Имя пользователя").fill(username)
            page.get_by_label("Пароль").fill(password)
            page.get_by_role("button", name="Войти").click()
            UI.expect_logged_in(page)

        @staticmethod
        def expect_logged_in(page) -> None:
            # The workspace URL plus the user chip (filled only after a
            # successful /api/auth/me/) prove that the session is really there.
            expect(page).to_have_url(f"{base_url}/", timeout=15_000)
            expect(page.locator("#current-user")).to_be_visible(timeout=15_000)
            expect(page.get_by_role("button", name="Выйти")).to_be_visible()
            expect(page.get_by_role("link", name="Войти")).to_be_hidden()

        @staticmethod
        def logout(page) -> None:
            page.get_by_role("button", name="Выйти").click()
            expect(page).to_have_url(f"{base_url}/login/", timeout=15_000)
            expect(page.locator("#current-user")).to_be_hidden()

        @staticmethod
        def open_task(page, task_id: int) -> None:
            page.goto(f"{base_url}/tasks/{task_id}/")
            expect(page.locator("#task-detail")).to_be_visible(timeout=15_000)

        @staticmethod
        def toast(page):
            return page.locator("#toast")

    return UI()


@pytest.fixture
def browser_events(page):
    """Collect console errors, uncaught JS errors and failed requests."""
    events: dict[str, list[str]] = {
        "console_errors": [],
        "page_errors": [],
        "failed_requests": [],
    }
    page.on(
        "console",
        lambda message: events["console_errors"].append(message.text)
        if message.type == "error"
        else None,
    )
    page.on("pageerror", lambda error: events["page_errors"].append(str(error)))
    page.on(
        "requestfailed",
        lambda request: events["failed_requests"].append(f"{request.method} {request.url}"),
    )
    return events


@pytest.fixture
def assert_clean_browser(browser_events):
    """Assert the page produced no JS/console/network errors.

    Chromium logs every non-2xx response of a *page* request as a console
    error. Tests that deliberately provoke an HTTP error (wrong password,
    forbidden action, foreign object) must declare that exact status via
    ``allow_http_statuses``; any other console error, any uncaught JS
    exception and any network-level failure still fails the test.
    """

    http_error_re = re.compile(
        r"Failed to load resource: the server responded with a status of (\d+)"
    )

    def _assert(allow_http_statuses: tuple[int, ...] = ()) -> None:
        assert browser_events["page_errors"] == [], (
            f"uncaught JS errors: {browser_events['page_errors']}"
        )
        unexpected_console = []
        for message in browser_events["console_errors"]:
            match = http_error_re.search(message)
            if match and int(match.group(1)) in allow_http_statuses:
                continue
            unexpected_console.append(message)
        assert unexpected_console == [], f"console errors: {unexpected_console}"
        assert browser_events["failed_requests"] == [], (
            f"failed requests: {browser_events['failed_requests']}"
        )

    return _assert
