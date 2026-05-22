from __future__ import annotations

import uuid

from app.domain.auth import (
    ROLE_ADMIN,
    ROLE_USER,
    InactiveUserError,
    InvalidCredentialsError,
    PermissionDeniedError,
    UserAlreadyExistsError,
)
from app.infra.security import create_access_token, hash_password, verify_password
from app.infra.tracing import get_tracer
from app.repositories.users import UserRepository


async def register_user(repo: UserRepository, email: str, password: str) -> dict:
    with get_tracer().start_span("auth.register") as span:
        span.set_attribute(
            "auth.email_domain", email.split("@")[-1] if "@" in email else ""
        )
        existing = await repo.get_by_email(email)
        if existing is not None:
            raise UserAlreadyExistsError(email)
        user = await repo.create(
            email=email,
            hashed_password=hash_password(password),
            role=ROLE_USER,
        )
        await repo.commit()
        return _user_to_dict(user)


async def login_user(
    repo: UserRepository, email: str, password: str, jwt_secret: str
) -> dict:
    with get_tracer().start_span("auth.login") as span:
        span.set_attribute(
            "auth.email_domain", email.split("@")[-1] if "@" in email else ""
        )
        user = await repo.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError("invalid credentials")
        if not user.is_active:
            raise InactiveUserError(email)
        token = create_access_token(
            {"sub": str(user.id), "role": user.role}, jwt_secret
        )
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": _user_to_dict(user),
        }


async def get_current_user_by_id(repo: UserRepository, user_id: str) -> dict:
    with get_tracer().start_span("auth.me") as span:
        span.set_attribute("auth.user_id", user_id)
        try:
            uid = uuid.UUID(user_id)
        except ValueError:
            raise InvalidCredentialsError("invalid user id in token")
        user = await repo.get_by_id(uid)
        if user is None:
            raise InvalidCredentialsError("user not found")
        if not user.is_active:
            raise InactiveUserError(user_id)
        return _user_to_dict(user)


def require_role(user: dict, required_role: str) -> None:
    """Raise PermissionDeniedError if user does not have required_role.

    Admin satisfies any role requirement.
    """
    if user.get("role") == ROLE_ADMIN:
        return
    if user.get("role") != required_role:
        raise PermissionDeniedError(f"role '{required_role}' required")


def _user_to_dict(user: object) -> dict:
    return {
        "id": user.id,  # type: ignore[attr-defined]
        "email": user.email,  # type: ignore[attr-defined]
        "role": user.role,  # type: ignore[attr-defined]
        "is_active": user.is_active,  # type: ignore[attr-defined]
    }
