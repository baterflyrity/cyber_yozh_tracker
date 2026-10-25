"""Comment access rules, nested URLs and validation (SPEC section 9, items 10-13)."""

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.tasks.models import Comment, Task
from apps.tests_helpers import bearer

User = get_user_model()


class CommentTestCase(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="S3cure-Pass!")
        self.worker = User.objects.create_user(username="worker", password="S3cure-Pass!")
        self.outsider = User.objects.create_user(username="outsider", password="S3cure-Pass!")
        self.task = Task.objects.create(
            title="Shared task", created_by=self.owner, assigned_to=self.worker
        )
        self.other_task = Task.objects.create(title="Other task", created_by=self.outsider)

    def as_user(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=bearer(user))
        return self.client

    def comments_url(self, task=None):
        return f"/api/tasks/{(task or self.task).pk}/comments/"

    def make_comment(self, author=None, body="Hello team"):
        return Comment.objects.create(task=self.task, author=author or self.owner, body=body)


class CommentAccessTests(CommentTestCase):
    def test_anonymous_cannot_read_or_write_comments(self):
        self.make_comment()
        url = self.comments_url()
        self.assertEqual(self.client.get(url).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            self.client.post(url, {"body": "hi"}, format="json").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_participants_can_list_and_create(self):
        client = self.as_user(self.owner)
        created = client.post(self.comments_url(), {"body": "from owner"}, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.assertEqual(created.data["author"]["username"], "owner")
        self.assertEqual(created.data["task"], self.task.pk)

        worker_client = self.as_user(self.worker)
        listing = worker_client.get(self.comments_url())
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(listing.data["count"], 1)

        created = worker_client.post(self.comments_url(), {"body": "from worker"}, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)

    def test_outsider_cannot_read_or_comment(self):
        self.make_comment()
        client = self.as_user(self.outsider)
        self.assertEqual(
            client.get(self.comments_url()).status_code, status.HTTP_404_NOT_FOUND
        )
        self.assertEqual(
            client.post(self.comments_url(), {"body": "intrusion"}, format="json").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertFalse(Comment.objects.filter(body="intrusion").exists())

    def test_former_assignee_loses_access_after_reassignment(self):
        self.make_comment()
        Task.objects.filter(pk=self.task.pk).update(assigned_to=self.outsider)
        client = self.as_user(self.worker)
        self.assertEqual(client.get(self.comments_url()).status_code, status.HTTP_404_NOT_FOUND)


class CommentMutationTests(CommentTestCase):
    def test_author_can_edit_own_comment(self):
        comment = self.make_comment(author=self.owner)
        client = self.as_user(self.owner)
        response = client.patch(
            f"{self.comments_url()}{comment.pk}/", {"body": "updated"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        comment.refresh_from_db()
        self.assertEqual(comment.body, "updated")

    def test_other_participant_cannot_edit_or_delete_comment(self):
        comment = self.make_comment(author=self.owner)
        client = self.as_user(self.worker)

        edit = client.patch(
            f"{self.comments_url()}{comment.pk}/", {"body": "hijacked"}, format="json"
        )
        self.assertEqual(edit.status_code, status.HTTP_403_FORBIDDEN)

        delete = client.delete(f"{self.comments_url()}{comment.pk}/")
        self.assertEqual(delete.status_code, status.HTTP_403_FORBIDDEN)

        comment.refresh_from_db()
        self.assertEqual(comment.body, "Hello team")

    def test_author_can_delete_own_comment(self):
        comment = self.make_comment(author=self.worker)
        client = self.as_user(self.worker)
        response = client.delete(f"{self.comments_url()}{comment.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Comment.objects.filter(pk=comment.pk).exists())

    def test_comment_task_cannot_be_reassigned_via_body(self):
        comment = self.make_comment(author=self.owner)
        client = self.as_user(self.owner)
        response = client.patch(
            f"{self.comments_url()}{comment.pk}/",
            {"body": "moved", "task": self.other_task.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        comment.refresh_from_db()
        self.assertEqual(comment.task_id, self.task.pk)
        self.assertEqual(comment.body, "moved")

    def test_nested_task_id_is_checked(self):
        comment = self.make_comment(author=self.owner)
        client = self.as_user(self.owner)

        # Foreign task URL: the caller is not a participant of it.
        foreign_url = f"/api/tasks/{self.other_task.pk}/comments/{comment.pk}/"
        self.assertEqual(client.get(foreign_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            client.patch(foreign_url, {"body": "x"}, format="json").status_code,
            status.HTTP_404_NOT_FOUND,
        )

        # Another visible task of the same user does not expose the comment either.
        own_other = Task.objects.create(title="Another own task", created_by=self.owner)
        own_other_url = f"/api/tasks/{own_other.pk}/comments/{comment.pk}/"
        self.assertEqual(client.get(own_other_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            client.post(
                f"/api/tasks/{own_other.pk}/comments/", {"body": "x"}, format="json"
            ).status_code,
            status.HTTP_201_CREATED,
        )

    def test_put_is_not_supported(self):
        comment = self.make_comment()
        client = self.as_user(self.owner)
        response = client.put(
            f"{self.comments_url()}{comment.pk}/", {"body": "full"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class CommentValidationTests(CommentTestCase):
    def test_blank_body_is_rejected(self):
        client = self.as_user(self.owner)
        response = client.post(self.comments_url(), {"body": "   "}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("body", response.data)

    def test_missing_body_is_rejected(self):
        client = self.as_user(self.owner)
        response = client.post(self.comments_url(), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("body", response.data)

    def test_too_long_body_is_rejected(self):
        client = self.as_user(self.owner)
        response = client.post(self.comments_url(), {"body": "x" * 5001}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("body", response.data)

    def test_deleting_task_cascades_to_comments(self):
        self.make_comment()
        self.as_user(self.owner)
        response = self.client.delete(f"/api/tasks/{self.task.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Comment.objects.filter(task=self.task).exists())
