from __future__ import annotations

ROLE_USER = "user"
ROLE_ADMIN = "admin"
VALID_ROLES = (ROLE_USER, ROLE_ADMIN)


class UserNotFoundError(RuntimeError):
    """Raised when a user lookup finds no matching record."""


class UserAlreadyExistsError(RuntimeError):
    """Raised when creating a user with a duplicate email."""


class InvalidCredentialsError(RuntimeError):
    """Raised when supplied credentials do not match stored values."""


class InactiveUserError(RuntimeError):
    """Raised when an inactive user attempts an authenticated operation."""


class PermissionDeniedError(RuntimeError):
    """Raised when a user lacks the required role for an operation."""
