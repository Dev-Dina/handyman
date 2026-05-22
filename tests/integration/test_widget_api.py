"""Integration tests: widget config API endpoints."""

from __future__ import annotations

import ast
import inspect
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auth import require_authenticated_user
from app.api.routes.widgets import router, _require_admin
from app.domain.auth import ROLE_ADMIN, ROLE_USER
from app.domain.widgets import WidgetInactiveError, WidgetNotFoundError
from app.infra.db import get_db_session

pytestmark = pytest.mark.integration

_ADMIN_UID = uuid.UUID("00000000-0000-0000-0000-000000000010")
_USER_UID = uuid.UUID("00000000-0000-0000-0000-000000000011")
_PUBLIC_WID = uuid.UUID("00000000-0000-0000-0000-000000000020")
_WIDGET_ID = uuid.UUID("00000000-0000-0000-0000-000000000021")
_NOW = datetime(2026, 5, 22, 0, 0, 0)

_ADMIN_USER = {
    "id": _ADMIN_UID,
    "email": "admin@example.com",
    "role": ROLE_ADMIN,
    "is_active": True,
}
_PLAIN_USER = {
    "id": _USER_UID,
    "email": "user@example.com",
    "role": ROLE_USER,
    "is_active": True,
}

_WIDGET_DICT = {
    "id": _WIDGET_ID,
    "public_widget_id": _PUBLIC_WID,
    "owner_user_id": _ADMIN_UID,
    "allowed_origins": ["https://demo.example.com"],
    "theme": {"color": "#fff"},
    "greeting": "Hello",
    "enabled_tools": ["rag_query"],
    "is_active": True,
    "created_at": _NOW,
    "updated_at": _NOW,
}


async def _noop_db():
    yield MagicMock()


@pytest.fixture(scope="module")
def client():
    """Client with admin auth and DB overridden."""
    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_db_session] = _noop_db
    test_app.dependency_overrides[require_authenticated_user] = lambda: _ADMIN_USER
    test_app.dependency_overrides[_require_admin] = lambda: _ADMIN_USER
    with TestClient(test_app) as c:
        yield c


@pytest.fixture(scope="module")
def noauth_client():
    """Client with no auth override — non-admin user."""
    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_db_session] = _noop_db
    test_app.dependency_overrides[require_authenticated_user] = lambda: _PLAIN_USER
    # _require_admin NOT overridden — will call require_role which should 403
    with TestClient(test_app) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /api/v1/widgets/{public_widget_id}  (public)
# ---------------------------------------------------------------------------


def test_public_widget_returns_200(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.widgets.get_public_widget",
        AsyncMock(return_value=_WIDGET_DICT),
    )
    monkeypatch.setattr("app.api.routes.widgets.check_origin", lambda w, o: None)
    r = client.get(f"/api/v1/widgets/{_PUBLIC_WID}")
    assert r.status_code == 200
    data = r.json()
    assert data["is_active"] is True
    assert "public_widget_id" in data


def test_public_inactive_widget_returns_404(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.widgets.get_public_widget",
        AsyncMock(side_effect=WidgetInactiveError("inactive")),
    )
    r = client.get(f"/api/v1/widgets/{_PUBLIC_WID}")
    assert r.status_code == 404


def test_public_unknown_widget_returns_404(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.widgets.get_public_widget",
        AsyncMock(side_effect=WidgetNotFoundError("gone")),
    )
    r = client.get(f"/api/v1/widgets/{_PUBLIC_WID}")
    assert r.status_code == 404


def test_public_widget_allowed_origin_passes(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.widgets.get_public_widget",
        AsyncMock(return_value=_WIDGET_DICT),
    )
    monkeypatch.setattr("app.api.routes.widgets.check_origin", lambda w, o: None)
    r = client.get(
        f"/api/v1/widgets/{_PUBLIC_WID}",
        headers={"origin": "https://demo.example.com"},
    )
    assert r.status_code == 200


def test_public_widget_denied_origin_returns_403(client, monkeypatch):
    from app.domain.widgets import WidgetOriginDeniedError

    monkeypatch.setattr(
        "app.api.routes.widgets.get_public_widget",
        AsyncMock(return_value=_WIDGET_DICT),
    )
    monkeypatch.setattr(
        "app.api.routes.widgets.check_origin",
        lambda w, o: (_ for _ in ()).throw(WidgetOriginDeniedError("denied")),
    )
    r = client.get(
        f"/api/v1/widgets/{_PUBLIC_WID}",
        headers={"origin": "https://evil.com"},
    )
    assert r.status_code == 403


def test_public_widget_has_csp_header(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.widgets.get_public_widget",
        AsyncMock(return_value=_WIDGET_DICT),
    )
    monkeypatch.setattr("app.api.routes.widgets.check_origin", lambda w, o: None)
    r = client.get(f"/api/v1/widgets/{_PUBLIC_WID}")
    assert r.status_code == 200
    assert "content-security-policy" in r.headers


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------


def test_admin_list_widgets_returns_200(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.widgets.list_admin_widgets",
        AsyncMock(return_value=[_WIDGET_DICT]),
    )
    r = client.get("/api/v1/admin/widgets")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) == 1


def test_admin_create_widget_returns_201(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.widgets.create_widget",
        AsyncMock(return_value=_WIDGET_DICT),
    )
    r = client.post(
        "/api/v1/admin/widgets",
        json={
            "allowed_origins": ["https://demo.example.com"],
            "enabled_tools": ["rag_query"],
        },
    )
    assert r.status_code == 201
    assert r.json()["is_active"] is True


def test_admin_create_non_admin_returns_403(noauth_client, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.widgets.create_widget",
        AsyncMock(return_value=_WIDGET_DICT),
    )
    r = noauth_client.post(
        "/api/v1/admin/widgets",
        json={"allowed_origins": []},
    )
    assert r.status_code == 403


def test_admin_update_widget_returns_200(client, monkeypatch):
    updated = {**_WIDGET_DICT, "greeting": "Updated"}
    monkeypatch.setattr(
        "app.api.routes.widgets.update_widget",
        AsyncMock(return_value=updated),
    )
    r = client.patch(
        f"/api/v1/admin/widgets/{_WIDGET_ID}",
        json={"greeting": "Updated"},
    )
    assert r.status_code == 200
    assert r.json()["greeting"] == "Updated"


# ---------------------------------------------------------------------------
# Architecture guards
# ---------------------------------------------------------------------------


def test_no_orm_model_import_in_widget_route() -> None:
    from app.api.routes import widgets as mod

    tree = ast.parse(inspect.getsource(mod))
    imported = [
        node.names[0].name if isinstance(node, ast.Import) else (node.module or "")
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    assert not any("app.infra.models" in name for name in imported)


def test_no_httpexception_in_widget_service() -> None:
    from app.services.widgets import service as mod

    tree = ast.parse(inspect.getsource(mod))
    imported = [
        node.names[0].name if isinstance(node, ast.Import) else (node.module or "")
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    assert not any("HTTPException" in name for name in imported)
