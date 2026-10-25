"""Helpers shared by the API tests."""

from rest_framework_simplejwt.tokens import RefreshToken


def bearer(user) -> str:
    """Build an ``Authorization: Bearer ...`` header value for ``user``."""
    return f"Bearer {RefreshToken.for_user(user).access_token}"
