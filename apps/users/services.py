"""Domain services for user registration.

Services receive plain arguments and never depend on HTTP/DRF objects.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

User = get_user_model()


def register_user(*, username: str, password: str, email: str = ""):
    """Create a new regular user with a properly hashed password.

    Raises ``django.core.exceptions.ValidationError`` for invalid passwords and
    rejects duplicate usernames. Privileged fields (``is_staff``,
    ``is_superuser``, ``is_active``) are never accepted from callers.
    """
    username = (username or "").strip()
    if not username:
        raise ValidationError("Username is required.")
    if User.objects.filter(username=username).exists():
        raise ValidationError("A user with that username already exists.")
    validate_password(password)
    return User.objects.create_user(
        username=username,
        email=(email or "").strip(),
        password=password,
    )
