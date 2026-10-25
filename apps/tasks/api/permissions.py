"""DRF permission classes for the tasks API.

Object-level rules are enforced by the shared policy helpers from
``apps/tasks.services`` so the API and the domain layer cannot drift apart:
views narrow the queryset to the caller's scope (404 for foreign objects) and
the services decide which operations are allowed (403).
"""

from rest_framework.permissions import BasePermission

from ..services import is_participant


class IsTaskParticipant(BasePermission):
    """Read/write access to a task requires being its creator or assignee."""

    message = "You do not have access to this task."

    def has_object_permission(self, request, view, obj):
        return is_participant(obj, request.user)


class IsCommentParticipant(BasePermission):
    """Access to a comment requires access to the related task."""

    message = "You do not have access to the related task."

    def has_object_permission(self, request, view, obj):
        return is_participant(obj.task, request.user)
