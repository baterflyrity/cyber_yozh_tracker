"""Serializers for tasks and comments (transport-level validation only)."""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .. import services
from ..models import Comment, Task

User = get_user_model()


class UserRefField(serializers.PrimaryKeyRelatedField):
    """Accepts a user id on write, returns ``{id, username}`` on read."""

    def use_pk_only_optimization(self):
        # The full user row is needed to build the {id, username} payload.
        return False

    def to_representation(self, value):
        if value is None:
            return None
        return {"id": value.pk, "username": value.username}


class TaskSerializer(serializers.ModelSerializer):
    created_by = UserRefField(read_only=True, help_text="Set by the server from the request user.")
    assigned_to = UserRefField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        allow_null=True,
        help_text="Active user id or null. Unassign with an explicit null.",
    )

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "description",
            "created_by",
            "assigned_to",
            "is_completed",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def validate_title(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        return value


class CommentSerializer(serializers.ModelSerializer):
    author = UserRefField(read_only=True, help_text="Set by the server from the request user.")
    task = serializers.PrimaryKeyRelatedField(
        read_only=True, help_text="Derived from the nested URL; cannot be changed by the body."
    )

    class Meta:
        model = Comment
        fields = ["id", "task", "author", "body", "created_at", "updated_at"]
        read_only_fields = ["id", "task", "author", "created_at", "updated_at"]

    def validate_body(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        if len(value) > services.MAX_COMMENT_LENGTH:
            raise serializers.ValidationError(
                f"Ensure this field has no more than {services.MAX_COMMENT_LENGTH} characters."
            )
        return value
