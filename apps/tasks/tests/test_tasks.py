"""Task CRUD, access rules, filters, pagination (SPEC section 9, items 2-9, 13)."""

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.tasks.models import Task
from apps.tests_helpers import bearer

User = get_user_model()

TASKS_URL = "/api/tasks/"


class TaskAPITestCase(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="S3cure-Pass!")
        self.worker = User.objects.create_user(username="worker", password="S3cure-Pass!")
        self.outsider = User.objects.create_user(username="outsider", password="S3cure-Pass!")
        self.inactive = User.objects.create_user(
            username="inactive", password="S3cure-Pass!", is_active=False
        )

    def as_user(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=bearer(user))
        return self.client

    def make_task(self, **kwargs):
        defaults = {"title": "Default task", "created_by": self.owner}
        defaults.update(kwargs)
        return Task.objects.create(**defaults)


class AuthenticationTests(TaskAPITestCase):
    def test_anonymous_cannot_read_or_write(self):
        self.assertEqual(self.client.get(TASKS_URL).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            self.client.post(TASKS_URL, {"title": "x"}, format="json").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        task = self.make_task()
        self.assertEqual(
            self.client.get(f"{TASKS_URL}{task.pk}/").status_code, status.HTTP_401_UNAUTHORIZED
        )
        self.assertEqual(
            self.client.patch(f"{TASKS_URL}{task.pk}/", {"is_completed": True}, format="json").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.delete(f"{TASKS_URL}{task.pk}/").status_code, status.HTTP_401_UNAUTHORIZED
        )


class TaskCreateTests(TaskAPITestCase):
    def test_creator_comes_from_request_user(self):
        self.as_user(self.worker)
        response = self.client.post(
            TASKS_URL,
            {"title": "My task", "description": "text", "created_by": self.owner.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        task = Task.objects.get(pk=response.data["id"])
        self.assertEqual(task.created_by, self.worker)
        self.assertEqual(response.data["created_by"]["username"], "worker")

    def test_creator_payload_cannot_be_overridden(self):
        self.as_user(self.worker)
        response = self.client.post(
            TASKS_URL, {"title": "T", "created_by": {"id": self.owner.pk}}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["created_by"]["username"], "worker")

    def test_task_can_be_created_without_assignee(self):
        self.as_user(self.owner)
        response = self.client.post(TASKS_URL, {"title": "Unassigned"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.data["assigned_to"])

    def test_assign_to_existing_active_user(self):
        self.as_user(self.owner)
        response = self.client.post(
            TASKS_URL, {"title": "For worker", "assigned_to": self.worker.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["assigned_to"], {"id": self.worker.pk, "username": "worker"})

    def test_assign_to_unknown_user_is_validation_error(self):
        self.as_user(self.owner)
        response = self.client.post(
            TASKS_URL, {"title": "Bad", "assigned_to": 999999}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("assigned_to", response.data)

    def test_assign_to_inactive_user_is_validation_error(self):
        self.as_user(self.owner)
        response = self.client.post(
            TASKS_URL, {"title": "Bad", "assigned_to": self.inactive.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("assigned_to", response.data)

    def test_blank_title_is_rejected(self):
        self.as_user(self.owner)
        response = self.client.post(TASKS_URL, {"title": "   "}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("title", response.data)

    def test_too_long_title_is_rejected(self):
        self.as_user(self.owner)
        response = self.client.post(TASKS_URL, {"title": "x" * 201}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("title", response.data)


class TaskAccessTests(TaskAPITestCase):
    def test_creator_reads_updates_and_deletes_own_task(self):
        task = self.make_task()
        client = self.as_user(self.owner)

        detail = client.get(f"{TASKS_URL}{task.pk}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)

        update = client.put(
            f"{TASKS_URL}{task.pk}/",
            {
                "title": "Updated",
                "description": "new description",
                "assigned_to": self.worker.pk,
                "is_completed": True,
            },
            format="json",
        )
        self.assertEqual(update.status_code, status.HTTP_200_OK, update.data)
        self.assertEqual(update.data["title"], "Updated")
        self.assertTrue(update.data["is_completed"])

        delete = client.delete(f"{TASKS_URL}{task.pk}/")
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Task.objects.filter(pk=task.pk).exists())

    def test_assignee_sees_task_and_toggles_completion(self):
        task = self.make_task(assigned_to=self.worker)
        client = self.as_user(self.worker)

        listing = client.get(TASKS_URL)
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertIn(task.pk, [item["id"] for item in listing.data["results"]])

        patch = client.patch(f"{TASKS_URL}{task.pk}/", {"is_completed": True}, format="json")
        self.assertEqual(patch.status_code, status.HTTP_200_OK, patch.data)
        self.assertTrue(patch.data["is_completed"])

        patch = client.patch(f"{TASKS_URL}{task.pk}/", {"is_completed": False}, format="json")
        self.assertEqual(patch.status_code, status.HTTP_200_OK)

    def test_assignee_cannot_change_other_fields(self):
        task = self.make_task(assigned_to=self.worker)
        client = self.as_user(self.worker)

        for payload in (
            {"title": "Hacked"},
            {"description": "hacked"},
            {"assigned_to": self.outsider.pk},
            {"title": "x", "description": "y", "assigned_to": self.outsider.pk, "is_completed": True},
        ):
            response = client.patch(f"{TASKS_URL}{task.pk}/", payload, format="json")
            self.assertEqual(
                response.status_code, status.HTTP_403_FORBIDDEN, (payload, response.data)
            )

        task.refresh_from_db()
        self.assertEqual(task.title, "Default task")
        self.assertEqual(task.assigned_to, self.worker)

    def test_assignee_cannot_delete_task(self):
        task = self.make_task(assigned_to=self.worker)
        client = self.as_user(self.worker)
        response = client.delete(f"{TASKS_URL}{task.pk}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Task.objects.filter(pk=task.pk).exists())

    def test_outsider_cannot_see_task_in_list_or_detail(self):
        task = self.make_task(assigned_to=self.worker)
        client = self.as_user(self.outsider)

        listing = client.get(TASKS_URL)
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertNotIn(task.pk, [item["id"] for item in listing.data["results"]])

        detail = client.get(f"{TASKS_URL}{task.pk}/")
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)

        patch = client.patch(f"{TASKS_URL}{task.pk}/", {"is_completed": True}, format="json")
        self.assertEqual(patch.status_code, status.HTTP_404_NOT_FOUND)

        delete = client.delete(f"{TASKS_URL}{task.pk}/")
        self.assertEqual(delete.status_code, status.HTTP_404_NOT_FOUND)

    def test_unassigned_task_is_invisible_to_everyone_but_creator(self):
        task = self.make_task()
        self.as_user(self.worker)
        self.assertEqual(
            self.client.get(f"{TASKS_URL}{task.pk}/").status_code, status.HTTP_404_NOT_FOUND
        )
        self.as_user(self.owner)
        self.assertEqual(
            self.client.get(f"{TASKS_URL}{task.pk}/").status_code, status.HTTP_200_OK
        )

    def test_reassignment_removes_access_from_previous_assignee(self):
        task = self.make_task(assigned_to=self.worker)
        self.as_user(self.owner)
        response = self.client.patch(
            f"{TASKS_URL}{task.pk}/", {"assigned_to": self.outsider.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.as_user(self.worker)
        self.assertEqual(
            self.client.get(f"{TASKS_URL}{task.pk}/").status_code, status.HTTP_404_NOT_FOUND
        )
        listing = self.client.get(TASKS_URL)
        self.assertNotIn(task.pk, [item["id"] for item in listing.data["results"]])

        self.as_user(self.outsider)
        self.assertEqual(
            self.client.get(f"{TASKS_URL}{task.pk}/").status_code, status.HTTP_200_OK
        )

    def test_creator_can_unassign_with_explicit_null(self):
        task = self.make_task(assigned_to=self.worker)
        self.as_user(self.owner)
        response = self.client.patch(f"{TASKS_URL}{task.pk}/", {"assigned_to": None}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        task.refresh_from_db()
        self.assertIsNone(task.assigned_to)


class TaskListTests(TaskAPITestCase):
    def test_filter_by_completion_status(self):
        done = self.make_task(title="Done task", is_completed=True)
        opened = self.make_task(title="Open task", is_completed=False)
        self.as_user(self.owner)

        completed = self.client.get(f"{TASKS_URL}?is_completed=true")
        self.assertEqual(completed.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in completed.data["results"]], [done.pk])

        active = self.client.get(f"{TASKS_URL}?is_completed=false")
        self.assertEqual(active.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in active.data["results"]], [opened.pk])

        invalid = self.client.get(f"{TASKS_URL}?is_completed=maybe")
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)

    def test_search_covers_title_and_description(self):
        by_title = self.make_task(title="Купить молоко")
        self.make_task(title="Другое", description="нужно купить хлеб")
        self.as_user(self.owner)

        response = self.client.get(f"{TASKS_URL}?search=купить")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        found = {item["id"] for item in response.data["results"]}
        self.assertEqual(found, {by_title.pk} | {Task.objects.get(title="Другое").pk})

    def test_ordering_by_created_at(self):
        first = self.make_task(title="First")
        second = self.make_task(title="Second")
        third = self.make_task(title="Third")
        self.as_user(self.owner)

        response = self.client.get(f"{TASKS_URL}?ordering=created_at")
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [first.pk, second.pk, third.pk])

        response = self.client.get(f"{TASKS_URL}?ordering=-created_at")
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [third.pk, second.pk, first.pk])

    def test_pagination_uses_page_size_twenty(self):
        for index in range(25):
            self.make_task(title=f"Task {index:02d}")
        self.as_user(self.owner)

        first_page = self.client.get(TASKS_URL)
        self.assertEqual(first_page.status_code, status.HTTP_200_OK)
        self.assertEqual(first_page.data["count"], 25)
        self.assertEqual(len(first_page.data["results"]), 20)

        second_page = self.client.get(f"{TASKS_URL}?page=2")
        self.assertEqual(len(second_page.data["results"]), 5)

    def test_list_returns_only_visible_tasks(self):
        mine = self.make_task(title="Mine")
        self.make_task(title="Foreign", created_by=self.outsider, assigned_to=self.outsider)
        self.as_user(self.owner)
        response = self.client.get(TASKS_URL)
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [mine.pk])
