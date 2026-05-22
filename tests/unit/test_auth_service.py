"""Unit tests for app/infra/security.py and app/services/auth.py."""

from __future__ import annotations

import time
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.auth import (
    ROLE_USER,
    InvalidCredentialsError,
    UserAlreadyExistsError,
)
from app.infra.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.services.auth import get_current_user_by_id, login_user, register_user

pytestmark = pytest.mark.unit

_SECRET = "test-signing-secret-for-unit-tests"
_UID = uuid.uuid4()


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def test_hash_password_is_not_plaintext():
    h = hash_password("mysecretpassword")
    assert "mysecretpassword" not in h


def test_verify_password_correct():
    h = hash_password("correct-horse-battery")
    assert verify_password("correct-horse-battery", h) is True


def test_verify_password_wrong():
    h = hash_password("correct-horse-battery")
    assert verify_password("wrong-password", h) is False


def test_verify_password_corrupt_stored():
    assert verify_password("anything", "notavalidhash") is False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------


def test_create_token_three_parts():
    token = create_access_token({"sub": "abc"}, _SECRET)
    assert token.count(".") == 2


def test_decode_token_round_trip():
    token = create_access_token({"sub": "user-123", "role": ROLE_USER}, _SECRET)
    claims = decode_access_token(token, _SECRET)
    assert claims["sub"] == "user-123"
    assert claims["role"] == ROLE_USER


def test_decode_token_wrong_secret():
    token = create_access_token({"sub": "x"}, _SECRET)
    with pytest.raises(InvalidCredentialsError):
        decode_access_token(token, "wrong-secret")


def test_decode_token_expired():
    token = create_access_token({"sub": "x"}, _SECRET, expire_minutes=0)
    # expire_minutes=0 sets exp = now; give it a moment to tick past
    time.sleep(0.01)
    with pytest.raises(InvalidCredentialsError, match="expired"):
        decode_access_token(token, _SECRET)


def test_decode_token_malformed():
    with pytest.raises(InvalidCredentialsError):
        decode_access_token("not.a.valid.jwt.at.all", _SECRET)


# ---------------------------------------------------------------------------
# register_user service
# ---------------------------------------------------------------------------


def _make_repo(existing_user=None, created_user=None):
    repo = MagicMock()
    repo.get_by_email = AsyncMock(return_value=existing_user)
    if created_user is None:
        mock_user = MagicMock()
        mock_user.id = _UID
        mock_user.email = "new@example.com"
        mock_user.role = ROLE_USER
        mock_user.is_active = True
        created_user = mock_user
    repo.create = AsyncMock(return_value=created_user)
    repo.commit = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=created_user)
    return repo


@pytest.mark.asyncio
async def test_register_creates_user():
    repo = _make_repo()
    result = await register_user(repo, "new@example.com", "strongpass1")
    repo.create.assert_awaited_once()
    repo.commit.assert_awaited_once()
    assert result["email"] == "new@example.com"
    assert result["role"] == ROLE_USER


@pytest.mark.asyncio
async def test_register_duplicate_raises():
    existing = MagicMock()
    repo = _make_repo(existing_user=existing)
    with pytest.raises(UserAlreadyExistsError):
        await register_user(repo, "dup@example.com", "strongpass1")


@pytest.mark.asyncio
async def test_register_always_sets_role_user():
    """Public register must not allow admin role creation."""
    repo = _make_repo()
    result = await register_user(repo, "new@example.com", "strongpass1")
    _, kwargs = repo.create.call_args
    assert kwargs.get("role") == ROLE_USER or repo.create.call_args[0][2] == ROLE_USER
    assert result["role"] == ROLE_USER


# ---------------------------------------------------------------------------
# login_user service
# ---------------------------------------------------------------------------


def _make_login_repo(user=None):
    repo = MagicMock()
    repo.get_by_email = AsyncMock(return_value=user)
    repo.commit = AsyncMock()
    return repo


@pytest.mark.asyncio
async def test_login_returns_token():
    hashed = hash_password("correct-pass")
    user = MagicMock()
    user.id = _UID
    user.email = "user@example.com"
    user.role = ROLE_USER
    user.is_active = True
    user.hashed_password = hashed
    repo = _make_login_repo(user=user)
    result = await login_user(repo, "user@example.com", "correct-pass", _SECRET)
    assert "access_token" in result
    assert result["token_type"] == "bearer"
    assert result["user"]["email"] == "user@example.com"


@pytest.mark.asyncio
async def test_login_wrong_password():
    hashed = hash_password("correct-pass")
    user = MagicMock()
    user.id = _UID
    user.email = "user@example.com"
    user.is_active = True
    user.hashed_password = hashed
    repo = _make_login_repo(user=user)
    with pytest.raises(InvalidCredentialsError):
        await login_user(repo, "user@example.com", "wrong-pass", _SECRET)


@pytest.mark.asyncio
async def test_login_unknown_email():
    repo = _make_login_repo(user=None)
    with pytest.raises(InvalidCredentialsError):
        await login_user(repo, "nobody@example.com", "any-pass", _SECRET)


# ---------------------------------------------------------------------------
# get_current_user_by_id service
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_current_user_by_id_ok():
    user = MagicMock()
    user.id = _UID
    user.email = "me@example.com"
    user.role = ROLE_USER
    user.is_active = True
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=user)
    result = await get_current_user_by_id(repo, str(_UID))
    assert result["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_get_current_user_invalid_uuid():
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=None)
    with pytest.raises(InvalidCredentialsError):
        await get_current_user_by_id(repo, "not-a-uuid")
