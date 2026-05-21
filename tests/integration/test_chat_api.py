"""Integration tests: POST /api/v1/chat endpoint with mocked Groq client."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.chat import router
from app.domain.errors import GroqUnavailableError, SecretNotFoundError

pytestmark = pytest.mark.integration

_NO_TOOL_RESPONSE = {
    "message": {
        "role": "assistant",
        "content": "Kubernetes pods are scheduled by the scheduler.",
        "tool_calls": None,
    }
}

_RAG_TOOL_CALL_RESPONSE = {
    "message": {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_001",
                "type": "function",
                "function": {
                    "name": "rag_query",
                    "arguments": json.dumps({"query": "pod scheduling"}),
                },
            }
        ],
    }
}

_AFTER_TOOL_RESPONSE = {
    "message": {
        "role": "assistant",
        "content": "Based on the Kubernetes docs, pod scheduling is handled by the kube-scheduler.",
        "tool_calls": None,
    }
}

_MOCK_CHUNK = {"text": "Pod scheduling docs.", "source_type": "docs", "score": 0.8}


@pytest.fixture(scope="module")
def client():
    test_app = FastAPI()
    test_app.include_router(router)
    with TestClient(test_app) as c:
        yield c


# ---------------------------------------------------------------------------
# Basic endpoint tests
# ---------------------------------------------------------------------------


def test_chat_ok_no_tools(client):
    mock_groq = AsyncMock()
    mock_groq.chat.return_value = _NO_TOOL_RESPONSE

    with patch(
        "app.api.routes.chat.run_chat",
        new=AsyncMock(
            return_value={
                "conversation_id": "conv_abc",
                "answer": "Kubernetes pods are scheduled by the scheduler.",
                "tool_calls": [],
                "model": "llama-3.3-70b-versatile",
                "latency_seconds": 0.5,
                "trace_id": None,
            }
        ),
    ):
        resp = client.post(
            "/api/v1/chat", json={"message": "How does pod scheduling work?"}
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "conversation_id" in data
    assert "tool_calls" in data
    assert "model" in data
    assert "latency_seconds" in data


def test_chat_response_shape(client):
    with patch(
        "app.api.routes.chat.run_chat",
        new=AsyncMock(
            return_value={
                "conversation_id": "conv_xyz",
                "answer": "The answer.",
                "tool_calls": [],
                "model": "llama-3.3-70b-versatile",
                "latency_seconds": 1.2,
                "trace_id": "abc123",
            }
        ),
    ):
        resp = client.post("/api/v1/chat", json={"message": "test question"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["conversation_id"] == "conv_xyz"
    assert data["answer"] == "The answer."
    assert data["model"] == "llama-3.3-70b-versatile"
    assert isinstance(data["latency_seconds"], float)
    assert data["trace_id"] == "abc123"


def test_chat_empty_message_rejected(client):
    resp = client.post("/api/v1/chat", json={"message": ""})
    assert resp.status_code == 422


def test_chat_missing_message_rejected(client):
    resp = client.post("/api/v1/chat", json={})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tool call tests (via orchestrator with injected client)
# ---------------------------------------------------------------------------


def test_chat_executes_rag_query_tool(client):
    mock_groq = AsyncMock()
    mock_groq.chat.side_effect = [_RAG_TOOL_CALL_RESPONSE, _AFTER_TOOL_RESPONSE]

    with (
        patch(
            "app.services.chat.orchestrator._load_groq_api_key",
            return_value="test-key",
        ),
        patch(
            "app.services.chat.orchestrator.GroqClient",
            return_value=mock_groq,
        ),
        patch(
            "app.services.chat.tool_registry.retrieve",
            new=AsyncMock(return_value=([_MOCK_CHUNK], "hybrid")),
        ),
    ):
        resp = client.post(
            "/api/v1/chat", json={"message": "how does pod scheduling work?"}
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["tool_calls"]) == 1
    assert data["tool_calls"][0]["tool_name"] == "rag_query"
    assert mock_groq.chat.call_count == 2


# ---------------------------------------------------------------------------
# Error mapping tests
# ---------------------------------------------------------------------------


def test_groq_unavailable_returns_503(client):
    with patch(
        "app.api.routes.chat.run_chat",
        new=AsyncMock(side_effect=GroqUnavailableError("Groq not configured")),
    ):
        resp = client.post("/api/v1/chat", json={"message": "hello"})

    assert resp.status_code == 503
    assert "detail" in resp.json()


def test_missing_groq_key_returns_503(client):
    with patch(
        "app.services.chat.orchestrator._load_groq_api_key",
        side_effect=SecretNotFoundError("groq_api_key not found in vault"),
    ):
        resp = client.post("/api/v1/chat", json={"message": "hello"})

    assert resp.status_code == 503


def test_unexpected_error_returns_500(client):
    with patch(
        "app.api.routes.chat.run_chat",
        new=AsyncMock(side_effect=RuntimeError("unexpected")),
    ):
        resp = client.post("/api/v1/chat", json={"message": "hello"})

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# Tool failure graceful handling
# ---------------------------------------------------------------------------


def test_tool_failure_does_not_crash_request(client):
    """A tool returning an error payload should not cause a 500."""
    mock_groq = AsyncMock()
    mock_groq.chat.side_effect = [
        {
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_fail",
                        "type": "function",
                        "function": {
                            "name": "summarize",
                            "arguments": json.dumps({"text": "issue body"}),
                        },
                    }
                ],
            }
        },
        {
            "message": {
                "role": "assistant",
                "content": "I could not summarize but here is my answer.",
                "tool_calls": None,
            }
        },
    ]

    from app.domain.errors import OllamaUnavailableError

    with (
        patch(
            "app.services.chat.orchestrator._load_groq_api_key",
            return_value="test-key",
        ),
        patch(
            "app.services.chat.orchestrator.GroqClient",
            return_value=mock_groq,
        ),
        patch(
            "app.services.chat.tool_registry.summarize_service",
            new=AsyncMock(side_effect=OllamaUnavailableError("ollama offline")),
        ),
    ):
        resp = client.post("/api/v1/chat", json={"message": "summarize this issue"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"]
    assert len(data["tool_calls"]) == 1


# ---------------------------------------------------------------------------
# Conversation ID passthrough
# ---------------------------------------------------------------------------


def test_conversation_id_preserved(client):
    with patch(
        "app.api.routes.chat.run_chat",
        new=AsyncMock(
            return_value={
                "conversation_id": "my-existing-conv",
                "answer": "yes",
                "tool_calls": [],
                "model": "llama-3.3-70b-versatile",
                "latency_seconds": 0.1,
                "trace_id": None,
            }
        ),
    ):
        resp = client.post(
            "/api/v1/chat",
            json={"message": "continue", "conversation_id": "my-existing-conv"},
        )

    assert resp.status_code == 200
    assert resp.json()["conversation_id"] == "my-existing-conv"


# ---------------------------------------------------------------------------
# Route registration smoke
# ---------------------------------------------------------------------------


def test_chat_route_registered():
    from app.main import app

    paths = {route.path for route in app.routes}
    assert "/api/v1/chat" in paths
