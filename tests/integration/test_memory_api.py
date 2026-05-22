"""Integration tests: /api/v1/memory/short-term and /long-term endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auth import require_authenticated_user
from app.api.routes.memory import router
from app.domain.auth import ROLE_USER
from app.domain.memory import RedisUnavailableError
from app.infra.db import get_db_session

pytestmark = pytest.mark.integration

_UID = uuid.UUID("00000000-0000-0000-0000-000000000099")
_MOCK_USER = {
    "id": _UID,
    "email": "inspector@example.com",
    "role": ROLE_USER,
    "is_active": True,
}
_CONV_ID = "conv-memory-test-001"

_ST_ITEMS = [
    {
        "role": "memory",
        "content": "Pods are scheduled by kube-scheduler.",
        "created_at": 1700000000,
    }
]
_LT_ITEMS = [
    {
        "memory_id": "mem-001",
        "content": "User prefers detailed explanations.",
        "memory_type": "episodic",
        "conversation_id": _CONV_ID,
        "created_at": "2026-05-22T00:00:00",
    }
]


async def _noop_db():
    yield MagicMock()


@pytest.fixture(scope="module")
def client():
    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_db_session] = _noop_db
    test_app.dependency_overrides[require_authenticated_user] = lambda: _MOCK_USER
    with TestClient(test_app) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /api/v1/memory/short-term
# ---------------------------------------------------------------------------


def test_short_term_returns_items(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.memory.read_memory",
        AsyncMock(return_value=_ST_ITEMS),
    )
    r = client.get("/api/v1/memory/short-term", params={"conversation_id": _CONV_ID})
    assert r.status_code == 200
    data = r.json()
    assert data["conversation_id"] == _CONV_ID
    assert len(data["items"]) == 1
    assert data["items"][0]["role"] == "memory"


def test_short_term_redis_unavailable_returns_empty(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.memory.read_memory",
        AsyncMock(side_effect=RedisUnavailableError("down")),
    )
    r = client.get("/api/v1/memory/short-term", params={"conversation_id": _CONV_ID})
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_short_term_missing_conversation_id_returns_422(client):
    r = client.get("/api/v1/memory/short-term")
    assert r.status_code == 422


def test_short_term_empty_redis_returns_empty_list(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.memory.read_memory",
        AsyncMock(return_value=[]),
    )
    r = client.get("/api/v1/memory/short-term", params={"conversation_id": _CONV_ID})
    assert r.status_code == 200
    assert r.json()["items"] == []


# ---------------------------------------------------------------------------
# GET /api/v1/memory/long-term
# ---------------------------------------------------------------------------


def test_long_term_returns_items_by_conversation(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.memory.list_long_term_memories",
        AsyncMock(return_value=_LT_ITEMS),
    )
    r = client.get("/api/v1/memory/long-term", params={"conversation_id": _CONV_ID})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["memory_type"] == "episodic"


def test_long_term_returns_items_by_user_when_no_conv(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.memory.list_long_term_memories",
        AsyncMock(return_value=_LT_ITEMS),
    )
    r = client.get("/api/v1/memory/long-term")
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1


def test_long_term_empty_returns_empty_list(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.memory.list_long_term_memories",
        AsyncMock(return_value=[]),
    )
    r = client.get("/api/v1/memory/long-term", params={"conversation_id": _CONV_ID})
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_memory_routes_require_auth():
    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_db_session] = _noop_db
    with TestClient(test_app) as c:
        r = c.get("/api/v1/memory/short-term", params={"conversation_id": "abc"})
    assert r.status_code == 401
