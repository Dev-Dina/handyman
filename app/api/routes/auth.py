"""HTTP-only layer for /api/v1/auth endpoints.

Validates HTTP input, calls auth service, maps domain errors to HTTP codes.
No business logic lives here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UserPublic,
)
from app.core.config import get_settings
from app.domain.auth import (
    InactiveUserError,
    InvalidCredentialsError,
    UserAlreadyExistsError,
)
from app.infra.db import get_db_session
from app.infra.logging import get_logger, request_id_var
from app.infra.security import decode_access_token
from app.repositories.users import UserRepository
from app.services.auth import get_current_user_by_id, login_user, register_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
logger = get_logger(__name__)

_bearer = HTTPBearer(auto_error=False)


async def require_authenticated_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """FastAPI dependency: decode JWT and return the current user dict.

    Raises HTTP 401 on missing/invalid/expired token or inactive user.
    """
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        jwt_secret = get_settings().secret("jwt_signing_key")
        claims = decode_access_token(creds.credentials, jwt_secret)
        user_id: str = claims["sub"]
    except (InvalidCredentialsError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    repo = UserRepository(session)
    try:
        return await get_current_user_by_id(repo, user_id)
    except (InvalidCredentialsError, InactiveUserError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post(
    "/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED
)
async def register(
    req: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
) -> UserPublic:
    req_id = request_id_var.get()
    repo = UserRepository(session)
    try:
        user_data = await register_user(repo, req.email, req.password)
    except UserAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    except Exception:
        logger.error("auth.register.unexpected_error", request_id=req_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )
    return UserPublic(**user_data)


@router.post("/login", response_model=LoginResponse)
async def login(
    req: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> LoginResponse:
    req_id = request_id_var.get()
    repo = UserRepository(session)
    try:
        jwt_secret = get_settings().secret("jwt_signing_key")
        result = await login_user(repo, req.email, req.password, jwt_secret)
    except (InvalidCredentialsError, InactiveUserError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    except Exception:
        logger.error("auth.login.unexpected_error", request_id=req_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )
    return LoginResponse(**result)


@router.get("/me", response_model=UserPublic)
async def me(current_user: dict = Depends(require_authenticated_user)) -> UserPublic:
    return UserPublic(**current_user)
