"""API-level exception handling.

Domain services are framework-friendly: they raise Django core exceptions
(``PermissionDenied`` and ``ValidationError``) instead of DRF responses. This
handler converts them into predictable DRF answers:

* ``PermissionDenied`` -> ``403``
* ``ValidationError`` -> ``400`` with a stable body
"""

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class DomainValidationError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid request data."
    default_code = "invalid"


def _flatten_validation_error(exc: DjangoValidationError) -> list[str]:
    messages = exc.messages if hasattr(exc, "messages") else [str(exc)]
    return list(messages)


def api_exception_handler(exc, context):
    """Extend the default DRF handler with Django core exceptions."""
    if isinstance(exc, DjangoPermissionDenied):
        return Response({"detail": str(exc) or "You do not have permission to perform this action."},
                        status=status.HTTP_403_FORBIDDEN)
    if isinstance(exc, DjangoValidationError):
        return Response({"detail": _flatten_validation_error(exc)},
                        status=status.HTTP_400_BAD_REQUEST)
    return drf_exception_handler(exc, context)
