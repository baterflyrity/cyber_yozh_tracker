"""Web application: HTML page shells only (no domain logic)."""

from django.apps import AppConfig


class WebConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "web"
    verbose_name = "Web"
