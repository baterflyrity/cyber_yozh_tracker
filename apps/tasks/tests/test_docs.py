"""OpenAPI schema/docs availability and demo seed idempotency (SPEC section 9, items 14)."""

import io

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.tasks.models import Comment, Task

User = get_user_model()


class SchemaTests(APITestCase):
    def test_schema_is_available(self):
        response = self.client.get("/api/schema/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode("utf-8")
        self.assertIn("openapi", content)
        self.assertIn("/api/tasks/", content)
        self.assertIn("bearerAuth", content)

    def test_swagger_ui_is_available(self):
        response = self.client.get("/api/docs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "swagger")

    def test_redoc_is_available(self):
        response = self.client.get("/api/redoc/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "redoc")


class SeedCommandTests(TestCase):
    def run_seed(self) -> str:
        out = io.StringIO()
        call_command("seed_demo_data", stdout=out)
        return out.getvalue()

    @override_settings(DEBUG=True)
    def test_seed_is_idempotent(self):
        self.run_seed()
        first = {
            "users": User.objects.count(),
            "tasks": Task.objects.count(),
            "comments": Comment.objects.count(),
        }
        self.run_seed()
        second = {
            "users": User.objects.count(),
            "tasks": Task.objects.count(),
            "comments": Comment.objects.count(),
        }
        self.assertEqual(first, second)
        self.assertEqual(first["users"], 3)
        self.assertEqual(first["tasks"], 3)
        self.assertGreaterEqual(first["comments"], 1)

    @override_settings(DEBUG=True)
    def test_seed_keeps_existing_passwords(self):
        self.run_seed()
        owner = User.objects.get(username="demo_owner")
        owner.set_password("ManuallyChanged123!")
        owner.save(update_fields=["password"])

        self.run_seed()
        owner.refresh_from_db()
        self.assertTrue(owner.check_password("ManuallyChanged123!"))

    @override_settings(DEBUG=True)
    def test_seed_accounts_are_not_staff(self):
        self.run_seed()
        for username in ("demo_owner", "demo_worker", "demo_outsider"):
            user = User.objects.get(username=username)
            self.assertFalse(user.is_staff)
            self.assertFalse(user.is_superuser)
            self.assertTrue(user.is_active)

    @override_settings(DEBUG=False)
    def test_seed_refuses_to_run_outside_debug(self):
        with self.assertRaises(CommandError):
            self.run_seed()
