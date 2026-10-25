"""Responsive layout and the three theme modes (system / light / dark)."""

import pytest
from conftest import DEMO_USERS
from playwright.sync_api import expect

VIEWPORTS = {
    "mobile": {"width": 390, "height": 844},
    "desktop": {"width": 1440, "height": 900},
}


def has_horizontal_scroll(page) -> bool:
    return page.evaluate(
        "Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)"
        " > window.innerWidth + 1"
    )


def assert_fits(page, label: str) -> None:
    assert not has_horizontal_scroll(page), f"unexpected horizontal scroll on {label}"


@pytest.mark.parametrize("viewport_name", list(VIEWPORTS))
def test_pages_have_no_horizontal_scroll_and_main_actions_are_reachable(
    page, ui, viewport_name
):
    size = VIEWPORTS[viewport_name]
    page.set_viewport_size(size)

    for path in ("/", "/login/", "/register/"):
        page.goto(ui.url(path))
        assert_fits(page, f"{path} @ {viewport_name}")

    ui.login(page, *DEMO_USERS["owner"])
    assert_fits(page, f"dashboard @ {viewport_name}")

    # Main actions are visible and reachable at this width.
    expect(page.get_by_role("button", name="Создать задачу")).to_be_visible()
    expect(page.get_by_label("Поиск")).to_be_visible()
    expect(page.get_by_label("Статус")).to_be_visible()
    expect(page.get_by_label("Тема оформления")).to_be_visible()

    # The task dialog fits into the viewport and can be closed with Escape.
    page.get_by_role("button", name="Создать задачу").click()
    dialog = page.locator("#task-dialog")
    expect(dialog).to_be_visible()
    box = dialog.bounding_box()
    assert box is not None
    assert box["width"] <= size["width"], "dialog is wider than the viewport"
    assert box["height"] <= size["height"] + 1, "dialog is taller than the viewport"
    page.keyboard.press("Escape")
    expect(dialog).to_be_hidden()

    # Task detail page also fits.
    first_card = page.locator(".task-card h2 a").first
    if page.locator(".task-card").count() == 0:
        # No tasks for this user: open the seeded one via search.
        page.get_by_label("Поиск").fill("Подготовить")
    expect(first_card).to_be_visible()
    first_card.click()
    expect(page.locator("#task-detail")).to_be_visible(timeout=15_000)
    assert_fits(page, f"task detail @ {viewport_name}")


def test_theme_modes_switch_and_persist(page, ui):
    page.goto(ui.url("/"))

    html = page.locator("html")
    theme_select = page.get_by_label("Тема оформления")

    # Default mode is "system".
    expect(html).to_have_attribute("data-theme-mode", "system")

    # Light theme.
    theme_select.select_option("light")
    expect(html).to_have_attribute("data-theme-mode", "light")
    expect(html).to_have_attribute("data-theme", "light")
    light_background = page.evaluate("getComputedStyle(document.body).backgroundColor")

    # Dark theme differs visually, not only by an attribute.
    theme_select.select_option("dark")
    expect(html).to_have_attribute("data-theme-mode", "dark")
    expect(html).to_have_attribute("data-theme", "dark")
    dark_background = page.evaluate("getComputedStyle(document.body).backgroundColor")
    assert dark_background != light_background, "dark theme must repaint the page"
    assert dark_background != "rgba(0, 0, 0, 0)", "page background must be defined"

    # Switching themes does not break the interface.
    expect(page.get_by_role("heading", name="Задачи")).to_be_visible()

    # The choice survives a reload.
    page.reload()
    expect(html).to_have_attribute("data-theme", "dark")
    expect(theme_select).to_have_value("dark")

    # Back to system mode follows prefers-color-scheme.
    theme_select.select_option("system")
    expect(html).to_have_attribute("data-theme-mode", "system")
    expected = page.evaluate(
        "window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'"
    )
    expect(html).to_have_attribute("data-theme", expected)


@pytest.mark.parametrize("color_scheme", ["dark", "light"])
def test_system_mode_follows_os_color_scheme(browser, base_url, color_scheme):
    context = browser.new_context(
        color_scheme=color_scheme, viewport={"width": 1280, "height": 720}
    )
    try:
        page = context.new_page()
        page.goto(f"{base_url}/")
        html = page.locator("html")
        expect(html).to_have_attribute("data-theme-mode", "system")
        expect(html).to_have_attribute("data-theme", color_scheme)
    finally:
        context.close()


def test_theme_choice_is_used_on_docs_pages_too(page, base_url):
    """Theme selector lives in the shared header of every page."""
    page.goto(f"{base_url}/login/")
    theme_select = page.get_by_label("Тема оформления")
    theme_select.select_option("dark")
    page.goto(f"{base_url}/register/")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    expect(page.get_by_label("Тема оформления")).to_have_value("dark")
