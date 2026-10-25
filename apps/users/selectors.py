"""Selector layer for users: the assignee directory."""

from django.contrib.auth import get_user_model
from django.db.models import QuerySet

User = get_user_model()


def active_users(search: str | None = None) -> QuerySet:
    """Active users available as task assignees, optionally filtered by name.

    Returns only what the assignment UI needs (``id`` and ``username`` are the
    serialized fields); passwords and other private data never leave the API.
    """
    queryset = User.objects.filter(is_active=True).order_by("username")
    if search:
        queryset = queryset.filter(username__icontains=search)
    return queryset
