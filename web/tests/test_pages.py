"""Browser page shells and static assets (SPEC section 9, item 15)."""

from django.contrib.staticfiles import finders
from rest_framework import status
from rest_framework.test import APITestCase


class PageTests(APITestCase):
    def test_dashboard_is_available_anonymously(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, 'id="task-list"')
        self.assertContains(response, "theme-select")
        # The shell must not leak any task data without an API call.
        self.assertNotContains(response, "Default task")

    def test_login_and_register_pages_open(self):
        login = self.client.get("/login/")
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertContains(login, 'id="login-form"')

        register = self.client.get("/register/")
        self.assertEqual(register.status_code, status.HTTP_200_OK)
        self.assertContains(register, 'id="register-form"')

    def test_task_detail_shell_opens(self):
        response = self.client.get("/tasks/42/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, 'id="task-detail"')
        self.assertContains(response, "window.__TASK_ID__ = 42")

    def test_unknown_page_returns_404(self):
        self.assertEqual(self.client.get("/nope/").status_code, 404)


class StaticAssetTests(APITestCase):
    REQUIRED_ASSETS = [
        "css/styles.css",
        "js/theme.js",
        "js/ui.js",
        "js/api.js",
        "js/pages/login.js",
        "js/pages/register.js",
        "js/pages/dashboard.js",
        "js/pages/task.js",
    ]

    def test_static_assets_are_resolvable(self):
        for path in self.REQUIRED_ASSETS:
            with self.subTest(path=path):
                found = finders.find(path)
                self.assertIsNotNone(found, f"static asset not found: {path}")

    def test_css_and_js_have_no_template_placeholders(self):
        for path in self.REQUIRED_ASSETS:
            with self.subTest(path=path):
                with open(finders.find(path), encoding="utf-8") as handle:
                    content = handle.read()
                self.assertNotIn("{% static", content)
                self.assertNotIn("TODO", content)
