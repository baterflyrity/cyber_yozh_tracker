"""Serializers for registration, the current user and the user directory."""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    """Registration payload.

    ``password`` is write-only and validated with Django's password
    validators; ``email`` is optional and explicitly unique (case-insensitive).
    """

    username = serializers.CharField(
        max_length=150,
        validators=[UniqueValidator(queryset=User.objects.all(), message="A user with that username already exists.")],
        help_text="Unique username.",
    )
    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
        help_text="Write-only; validated with Django password validators.",
    )
    email = serializers.EmailField(required=False, allow_blank=True, default="",
                                   help_text="Optional, unique (case-insensitive).")

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_email(self, value):
        value = (value or "").strip()
        if value and User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return value

    def validate_username(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        return value


class UserBriefSerializer(serializers.ModelSerializer):
    """Minimal representation used for ``/api/auth/me/``."""

    class Meta:
        model = User
        fields = ["id", "username", "email"]
        read_only_fields = fields


class UserDirectorySerializer(serializers.ModelSerializer):
    """Assignee directory entry: only id and username (spec section 3.1)."""

    class Meta:
        model = User
        fields = ["id", "username"]
        read_only_fields = fields
