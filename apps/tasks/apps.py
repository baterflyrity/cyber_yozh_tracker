"""Tasks application: tasks, comments, domain services and the REST API."""

from django.apps import AppConfig


class TasksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tasks"
    label = "tasks"
    verbose_name = "Tasks"
