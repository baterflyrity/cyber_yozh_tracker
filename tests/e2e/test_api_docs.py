"""Redoc and Swagger UI must render in a real browser without JS errors."""

from playwright.sync_api import expect


def _track_responses(page) -> dict:
    statuses: dict[str, int] = {}
    page.on("response", lambda response: statuses.__setitem__(response.url, response.status))
    return statuses


def test_redoc_renders_the_api_documentation(page, assert_clean_browser, base_url):
    statuses = _track_responses(page)
    page.goto(f"{base_url}/api/redoc/")

    container = page.locator("#redoc-container")
    expect(container).to_be_visible(timeout=20_000)
    # Real content: the API title and at least one endpoint path.
    expect(container).to_contain_text("CyberYozh Task Manager API", timeout=20_000)
    expect(container).to_contain_text("/api/tasks/")
    text = container.inner_text()
    assert len(text) > 500, f"Redoc container looks empty ({len(text)} chars)"

    # The schema endpoint answered successfully.
    schema_responses = [
        (url, status) for url, status in statuses.items() if "/api/schema/" in url
    ]
    assert schema_responses, "Redoc did not request the OpenAPI schema"
    assert all(status == 200 for _, status in schema_responses), schema_responses

    # The bundle is served from our own origin (version-pinned sidecar), no CDN.
    bundles = [(url, status) for url, status in statuses.items()
               if url.endswith("redoc.standalone.js")]
    assert bundles, "Redoc standalone bundle was not requested"
    assert all(status == 200 for _, status in bundles), bundles
    assert all(url.startswith(f"{base_url}/") for url, _ in bundles), bundles

    html = page.content()
    assert "cdn.jsdelivr.net" not in html, "Redoc must not depend on a CDN"
    assert "fonts.googleapis.com" not in html, "page must not load external fonts"

    # No uncaught exceptions (this is exactly where "import.meta" used to fail),
    # no console errors and no failed requests.
    assert_clean_browser()


def test_swagger_ui_renders_the_api_documentation(page, assert_clean_browser, base_url):
    statuses = _track_responses(page)
    page.goto(f"{base_url}/api/docs/")

    expect(page.locator("#swagger-ui")).to_be_visible(timeout=20_000)
    expect(page.locator(".swagger-ui .info .title")).to_contain_text(
        "CyberYozh Task Manager API", timeout=20_000
    )
    expect(page.locator(".opblock").first).to_be_visible(timeout=20_000)

    operations = page.locator(".opblock").count()
    assert operations >= 10, f"only {operations} operations rendered"

    schema_responses = [
        (url, status) for url, status in statuses.items() if "/api/schema/" in url
    ]
    assert schema_responses, "Swagger UI did not request the OpenAPI schema"
    assert all(status == 200 for _, status in schema_responses), schema_responses

    html = page.content()
    assert "cdn.jsdelivr.net" not in html, "Swagger UI must not depend on a CDN"

    assert_clean_browser()


def test_openapi_schema_endpoint_serves_valid_documentation(page, base_url, assert_clean_browser):
    response = page.request.get(f"{base_url}/api/schema/")
    assert response.status == 200
    body = response.text()
    assert "openapi:" in body
    assert "/api/tasks/" in body
    assert "bearerAuth" in body
