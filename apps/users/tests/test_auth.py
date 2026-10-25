"""Authentication, registration and the user directory (SPEC section 9, items 1-2)."""

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.tests_helpers import bearer

User = get_user_model()


class RegistrationTests(APITestCase):
    def test_register_creates_user_with_hashed_password(self):
        response = self.client.post(
            "/api/auth/register/",
            {"username": "newbie", "password": "S3cure-Pass!", "email": "newbie@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(set(response.data), {"id", "username", "email"})
        self.assertNotIn("password", response.data)

        user = User.objects.get(username="newbie")
        self.assertTrue(user.check_password("S3cure-Pass!"))
        self.assertNotEqual(user.password, "S3cure-Pass!")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_register_rejects_duplicate_username(self):
        User.objects.create_user(username="taken", password="S3cure-Pass!")
        response = self.client.post(
            "/api/auth/register/",
            {"username": "taken", "password": "S3cure-Pass!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)

    def test_register_rejects_duplicate_email(self):
        User.objects.create_user(username="a", password="S3cure-Pass!", email="dup@example.com")
        response = self.client.post(
            "/api/auth/register/",
            {"username": "b", "password": "S3cure-Pass!", "email": "DUP@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_register_rejects_weak_password(self):
        response = self.client.post(
            "/api/auth/register/", {"username": "weak", "password": "12345678"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_register_does_not_accept_privileged_fields(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "username": "sneaky",
                "password": "S3cure-Pass!",
                "is_staff": True,
                "is_superuser": True,
                "id": 999,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        user = User.objects.get(username="sneaky")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertNotEqual(user.pk, 999)


class TokenTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="S3cure-Pass!")

    def test_obtain_refresh_and_me(self):
        response = self.client.post(
            "/api/auth/token/",
            {"username": "alice", "password": "S3cure-Pass!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        refresh_response = self.client.post(
            "/api/auth/token/refresh/", {"refresh": response.data["refresh"]}, format="json"
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", refresh_response.data)

        me = self.client.get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(me.data["username"], "alice")
        self.assertNotIn("password", me.data)

    def test_token_rejects_bad_credentials(self):
        response = self.client.post(
            "/api/auth/token/", {"username": "alice", "password": "nope"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_requires_authentication(self):
        self.assertEqual(self.client.get("/api/auth/me/").status_code, status.HTTP_401_UNAUTHORIZED)


class UserDirectoryTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="S3cure-Pass!")
        self.bob = User.objects.create_user(username="bobby", password="S3cure-Pass!")
        self.inactive = User.objects.create_user(
            username="gone", password="S3cure-Pass!", is_active=False
        )

    def test_requires_authentication(self):
        self.assertEqual(self.client.get("/api/users/").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_only_id_and_username_of_active_users(self):
        response = self.client.get("/api/users/", HTTP_AUTHORIZATION=bearer(self.alice))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        names = {item["username"] for item in results}
        self.assertEqual(names, {"alice", "bobby"})
        self.assertNotIn("gone", names)
        for item in results:
            self.assertEqual(set(item), {"id", "username"})

    def test_search_filters_by_username(self):
        response = self.client.get(
            "/api/users/?search=bob", HTTP_AUTHORIZATION=bearer(self.alice)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["username"] for item in response.data["results"]], ["bobby"])
