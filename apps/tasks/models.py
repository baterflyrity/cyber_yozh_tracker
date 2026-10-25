"""Persistence models for tasks and comments.

Models describe data structure, relations, constraints and simple defaults
only; all business rules live in ``apps/tasks/services.py``.
"""

from django.conf import settings
from django.db import models


class Task(models.Model):
    """A task created by a user and optionally assigned to another user."""

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tasks_created",
        verbose_name="author",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks_assigned",
        verbose_name="assignee",
    )
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["created_by", "updated_at"], name="task_created_by_idx"),
            models.Index(fields=["assigned_to", "updated_at"], name="task_assigned_to_idx"),
        ]
        verbose_name = "task"
        verbose_name_plural = "tasks"

    def __str__(self) -> str:
        return self.title


class Comment(models.Model):
    """A comment attached to a task; cascade-deleted with it."""

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "comment"
        verbose_name_plural = "comments"

    def __str__(self) -> str:
        return f"Comment #{self.pk} on {self.task_id}"
