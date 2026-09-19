from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class DomainError(Exception):
    def __init__(self, code, message, *, http_status=status.HTTP_409_CONFLICT, fields=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.fields = fields


def _validation_fields(detail):
    if isinstance(detail, dict):
        return {key: value for key, value in detail.items()}
    return {"non_field_errors": detail if isinstance(detail, list) else [detail]}


def api_exception_handler(exc, context):
    if isinstance(exc, DomainError):
        payload = {"code": exc.code, "message": exc.message}
        if exc.fields is not None:
            payload["fields"] = exc.fields
        return Response({"error": payload}, status=exc.http_status)

    response = drf_exception_handler(exc, context)
    if response is None:
        if isinstance(exc, Http404):
            response = Response(status=status.HTTP_404_NOT_FOUND)
        elif isinstance(exc, DjangoPermissionDenied):
            response = Response(status=status.HTTP_403_FORBIDDEN)
        else:
            return None

    code = "VALIDATION_ERROR"
    message = "Some fields are invalid."
    fields = None
    if isinstance(exc, exceptions.NotAuthenticated):
        code, message = "AUTHENTICATION_REQUIRED", "Authentication is required."
    elif isinstance(exc, exceptions.AuthenticationFailed):
        code, message = "INVALID_CREDENTIALS", "The email or password is invalid."
    elif isinstance(exc, (exceptions.PermissionDenied, DjangoPermissionDenied)):
        raw = str(getattr(exc, "detail", exc))
        if raw.startswith("CSRF Failed"):
            code, message = "CSRF_FAILED", "CSRF validation failed."
        else:
            code, message = "PERMISSION_DENIED", "You do not have permission to perform this action."
    elif isinstance(exc, (exceptions.NotFound, Http404)) or response.status_code == 404:
        code, message = "NOT_FOUND", "The requested resource was not found."
    elif isinstance(exc, exceptions.Throttled):
        code, message = "RATE_LIMITED", "Too many requests. Please try again later."
    elif isinstance(exc, exceptions.ParseError):
        code, message = "VALIDATION_ERROR", "The request body is malformed."
    elif isinstance(exc, exceptions.ValidationError):
        fields = _validation_fields(exc.detail)

    payload = {"code": code, "message": message}
    if fields is not None:
        payload["fields"] = fields
    response.data = {"error": payload}
    return response
