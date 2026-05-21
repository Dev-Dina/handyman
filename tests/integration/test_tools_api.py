"""Integration tests: FastAPI endpoint behavior with mocked external infra.

Uses a bare FastAPI app with the tools router — no Vault lifespan, no real Ollama.
Summarize tests mock OllamaClient to avoid any network calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.tools import router
from app.domain.errors import OllamaUnavailableError

pytestmark = pytest.mark.integration

_ENTITY_KEYS = (
    "versions",
    "commands",
    "components",
    "errors",
    "resources",
    "paths",
    "images",
    "urls",
)


@pytest.fixture(scope="module")
def client():
    test_app = FastAPI()
    test_app.include_router(router)
    with TestClient(test_app) as c:
        yield c


# ---------------------------------------------------------------------------
# /entities
# ---------------------------------------------------------------------------


def test_entities_ok(client):
    resp = client.post("/api/v1/tools/entities", json={"text": "kubectl get pods"})
    assert resp.status_code == 200
    data = resp.json()
    assert "entities_by_type" in data
    assert "total_count" in data


def test_entities_response_structure(client):
    resp = client.post(
        "/api/v1/tools/entities",
        json={"text": "v1.29.0 CrashLoopBackOff on kubelet"},
    )
    assert resp.status_code == 200
    entities = resp.json()["entities_by_type"]
    for key in _ENTITY_KEYS:
        assert key in entities, f"Missing key: {key}"


def test_entities_all_values_lists(client):
    resp = client.post("/api/v1/tools/entities", json={"text": "some text"})
    for val in resp.json()["entities_by_type"].values():
        assert isinstance(val, list)


def test_entities_total_count_matches(client):
    resp = client.post("/api/v1/tools/entities", json={"text": "kubectl get pods"})
    data = resp.json()
    computed = sum(len(v) for v in data["entities_by_type"].values())
    assert data["total_count"] == computed


def test_entities_empty_text_rejected(client):
    resp = client.post("/api/v1/tools/entities", json={"text": ""})
    assert resp.status_code == 422


def test_entities_missing_text_rejected(client):
    resp = client.post("/api/v1/tools/entities", json={})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# /summarize
# ---------------------------------------------------------------------------


def test_summarize_ollama_unavailable_returns_503(client):
    with patch(
        "app.api.routes.tools.summarize_service",
        new=AsyncMock(side_effect=OllamaUnavailableError("unreachable")),
    ):
        resp = client.post(
            "/api/v1/tools/summarize", json={"text": "kubectl pod crash"}
        )
    assert resp.status_code == 503


def test_summarize_ok_with_mock(client):
    mock_result = {
        "summary": "1. Problem — pod crashes.\n2. Expected — stable.\n3. Evidence — OOMKilled.\n4. Component — kubelet.",
        "model": "llama3:latest",
        "latency_seconds": 0.1,
    }
    with patch(
        "app.api.routes.tools.summarize_service",
        new=AsyncMock(return_value=mock_result),
    ):
        resp = client.post(
            "/api/v1/tools/summarize", json={"text": "pod crashlooping due to OOM"}
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data
    assert "model" in data
    assert "latency_seconds" in data


def test_summarize_empty_text_rejected(client):
    resp = client.post("/api/v1/tools/summarize", json={"text": ""})
    assert resp.status_code == 422


def test_summarize_max_chars_respected_in_mock(client):
    long_summary = "x" * 2000
    mock_result = {
        "summary": long_summary,
        "model": "llama3:latest",
        "latency_seconds": 0.1,
    }
    with patch(
        "app.api.routes.tools.summarize_service",
        new=AsyncMock(return_value=mock_result),
    ):
        resp = client.post(
            "/api/v1/tools/summarize",
            json={"text": "pod crash", "max_chars": 500},
        )
    assert resp.status_code == 200
