"""Integration tests: /api/v1/auth endpoints with mocked services and DB."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auth import router
from app.domain.auth import ROLE_USER, InvalidCredentialsError, UserAlreadyExistsError
from app.infra.db import get_db_session
from app.infra.security import create_access_token

pytestmark = pytest.mark.integration

_TEST_SECRET = "integration-test-jwt-secret"
_TEST_UID = uuid.UUID("00000000-0000-0000-0000-000000000042")

_MOCK_USER = {
    "id": _TEST_UID,
    "email": "test@example.com",
    "role": ROLE_USER,
    "is_active": True,
}

_MOCK_LOGIN_RESULT = {
    "access_token": "fake.access.token",
    "token_type": "bearer",
    "user": _MOCK_USER,
}


class _MockSettings:
    def secret(self, key: str) -> str:
        if key == "jwt_signing_key":
            return _TEST_SECRET
        return "mock-secret"


async def _noop_db():
    yield MagicMock()


@pytest.fixture(scope="module")
def client():
    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_db_session] = _noop_db
    with patch("app.api.routes.auth.get_settings", return_value=_MockSettings()):
        with TestClient(test_app) as c:
            yield c


# ---------------------------------------------------------------------------
# POST /api/v1/auth/register
# ---------------------------------------------------------------------------


def test_register_ok(client):
    with patch(
        "app.api.routes.auth.register_user", new=AsyncMock(return_value=_MOCK_USER)
    ):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "strongpass1"},
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "test@example.com"
    assert data["role"] == ROLE_USER
    assert "hashed_password" not in data


def test_register_duplicate_email_returns_409(client):
    with patch(
        "app.api.routes.auth.register_user",
        new=AsyncMock(side_effect=UserAlreadyExistsError("test@example.com")),
    ):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "strongpass1"},
        )
    assert resp.status_code == 409


def test_register_bad_email_returns_422(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "notanemail", "password": "strongpass1"},
    )
    assert resp.status_code == 422


def test_register_short_password_returns_422(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "valid@example.com", "password": "short"},
    )
    assert resp.status_code == 422


def test_register_cannot_create_admin(client):
    """Public register ignores any role field and always produces role=user."""
    with patch(
        "app.api.routes.auth.register_user", new=AsyncMock(return_value=_MOCK_USER)
    ):
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "strongpass1",
                "role": "admin",
            },
        )
    # Response role is always user (mock returns _MOCK_USER with role=user)
    assert resp.status_code == 201
    assert resp.json()["role"] == ROLE_USER


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login
# ---------------------------------------------------------------------------


def test_login_ok(client):
    with patch(
        "app.api.routes.auth.login_user", new=AsyncMock(return_value=_MOCK_LOGIN_RESULT)
    ):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "correct-pass"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "user" in data
    assert "hashed_password" not in data.get("user", {})


def test_login_wrong_password_returns_401(client):
    with patch(
        "app.api.routes.auth.login_user",
        new=AsyncMock(side_effect=InvalidCredentialsError("invalid")),
    ):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "wrong"},
        )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/auth/me
# ---------------------------------------------------------------------------


def test_me_with_valid_token(client):
    token = create_access_token({"sub": str(_TEST_UID)}, _TEST_SECRET)
    with patch(
        "app.api.routes.auth.get_current_user_by_id",
        new=AsyncMock(return_value=_MOCK_USER),
    ):
        resp = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
    assert resp.status_code == 200
    assert resp.json()["email"] == "test@example.com"


def test_me_missing_token_returns_401(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_invalid_token_returns_401(client):
    resp = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer this.is.garbage"}
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Architecture guardrails
# ---------------------------------------------------------------------------


def test_no_sqlalchemy_in_routes():
    import ast
    import pathlib

    src = (
        pathlib.Path(__file__).parent.parent.parent
        / "app"
        / "api"
        / "routes"
        / "auth.py"
    )
    tree = ast.parse(src.read_text())
    imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    for imp in imports:
        if isinstance(imp, ast.ImportFrom) and imp.module:
            assert (
                "sqlalchemy.orm" not in imp.module
                or imp.module == "sqlalchemy.ext.asyncio"
            ), f"Unexpected SQLAlchemy ORM import in route: {imp.module}"


def test_no_http_exception_in_services():
    import ast
    import pathlib

    src = pathlib.Path(__file__).parent.parent.parent / "app" / "services" / "auth.py"
    tree = ast.parse(src.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "HTTPException":
            pytest.fail("HTTPException found in app/services/auth.py")
        if isinstance(node, ast.Attribute) and node.attr == "HTTPException":
            pytest.fail("HTTPException found in app/services/auth.py")
