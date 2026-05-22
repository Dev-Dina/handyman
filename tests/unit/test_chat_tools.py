"""Unit tests: chat tool registry and orchestrator structural checks."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Tool registry structural checks
# ---------------------------------------------------------------------------


def test_tool_registry_importable():
    from app.services.chat.tool_registry import TOOL_DEFINITIONS, ALL_TOOL_NAMES  # noqa: F401


def test_tool_definitions_has_expected_tools():
    from app.services.chat.tool_registry import ALL_TOOL_NAMES

    for name in (
        "rag_query",
        "extract_entities",
        "summarize",
        "classify_issue",
        "write_memory",
    ):
        assert name in ALL_TOOL_NAMES, f"Missing tool: {name}"


def test_tool_definitions_openai_format():
    from app.services.chat.tool_registry import TOOL_DEFINITIONS

    for td in TOOL_DEFINITIONS:
        assert td["type"] == "function"
        func = td["function"]
        assert "name" in func
        assert "description" in func
        assert "parameters" in func
        params = func["parameters"]
        assert params["type"] == "object"
        assert "properties" in params
        assert "required" in params


def test_no_torch_import_in_tool_registry():
    import sys

    import app.services.chat.tool_registry  # noqa: F401

    assert "torch" not in sys.modules, "torch must not be imported in tool_registry"


def test_no_torch_import_in_orchestrator():
    import sys

    import app.services.chat.orchestrator  # noqa: F401

    assert "torch" not in sys.modules, "torch must not be imported in orchestrator"


# ---------------------------------------------------------------------------
# Groq client structural checks
# ---------------------------------------------------------------------------


def test_groq_client_importable():
    from app.infra.groq_client import GroqClient  # noqa: F401


def test_groq_client_constants():
    from app.infra.groq_client import FALLBACK_MODEL, PRIMARY_MODEL

    assert PRIMARY_MODEL == "llama-3.3-70b-versatile"
    assert FALLBACK_MODEL  # not empty


def test_groq_unavailable_error_importable():
    from app.domain.errors import GroqUnavailableError  # noqa: F401


# ---------------------------------------------------------------------------
# write_memory — real Redis path and failure path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_memory_tool_stores_memory():
    from app.services.chat.tool_registry import dispatch_tool

    expected = {
        "status": "stored",
        "conversation_id": "conv-123",
        "memory_type": "short_term",
        "ttl_seconds": 86400,
    }
    with patch(
        "app.services.chat.tool_registry.store_memory",
        new=AsyncMock(return_value=expected),
    ):
        result = await dispatch_tool(
            "write_memory",
            {"content": "pods use namespace isolation"},
            ["write_memory"],
            conversation_id="conv-123",
        )

    data = json.loads(result)
    assert data["status"] == "stored"
    assert data["memory_type"] == "short_term"
    assert data["conversation_id"] == "conv-123"


@pytest.mark.asyncio
async def test_write_memory_tool_graceful_on_redis_failure():
    from app.domain.memory import RedisUnavailableError
    from app.services.chat.tool_registry import dispatch_tool

    with patch(
        "app.services.chat.tool_registry.store_memory",
        new=AsyncMock(side_effect=RedisUnavailableError("connection refused")),
    ):
        result = await dispatch_tool(
            "write_memory",
            {"content": "some fact"},
            ["write_memory"],
        )

    data = json.loads(result)
    assert data["status"] == "memory_unavailable"


# ---------------------------------------------------------------------------
# tool_not_enabled guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disabled_tool_returns_error():
    from app.services.chat.tool_registry import dispatch_tool

    result = await dispatch_tool("rag_query", {"query": "test"}, [])
    data = json.loads(result)
    assert data["error"] == "tool_not_enabled"
    assert data["tool"] == "rag_query"


# ---------------------------------------------------------------------------
# rag_query tool wraps retrieve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rag_query_tool_calls_retrieve():
    from app.services.chat.tool_registry import dispatch_tool

    mock_chunk = {"text": "Pod scheduling docs.", "source_type": "docs", "score": 0.9}
    with patch(
        "app.services.chat.tool_registry.retrieve",
        new=AsyncMock(return_value=([mock_chunk], "hybrid")),
    ):
        result = await dispatch_tool(
            "rag_query", {"query": "pod scheduling"}, ["rag_query"]
        )

    data = json.loads(result)
    assert data["retriever"] == "hybrid"
    assert len(data["results"]) == 1
    assert "text" in data["results"][0]


# ---------------------------------------------------------------------------
# classify_issue tool returns unavailable when modelserver is down
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_issue_unavailable_when_modelserver_down():
    from app.domain.errors import ModelServerUnavailableError
    from app.services.chat.tool_registry import dispatch_tool

    with patch(
        "app.infra.modelserver_client.ModelServerClient",
    ) as mock_cls:
        instance = AsyncMock()
        instance.classify.side_effect = ModelServerUnavailableError("not reachable")
        mock_cls.return_value = instance

        result = await dispatch_tool(
            "classify_issue",
            {"title": "Pod crash", "body": "CrashLoopBackOff"},
            ["classify_issue"],
        )

    data = json.loads(result)
    assert data["status"] == "tool_unavailable"
    assert data["tool"] == "classify_issue"
    assert data["reason"] == "model_server_not_ready"


# ---------------------------------------------------------------------------
# summarize tool returns error payload when Ollama is down
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summarize_tool_graceful_on_ollama_unavailable():
    from app.domain.errors import OllamaUnavailableError
    from app.services.chat.tool_registry import dispatch_tool

    with patch(
        "app.services.chat.tool_registry.summarize_service",
        new=AsyncMock(side_effect=OllamaUnavailableError("ollama not running")),
    ):
        result = await dispatch_tool(
            "summarize", {"text": "pod crash logs"}, ["summarize"]
        )

    data = json.loads(result)
    assert data["error"] == "summarize_unavailable"


# ---------------------------------------------------------------------------
# Orchestrator: missing Groq key raises GroqUnavailableError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_orchestrator_raises_on_missing_groq_key():
    from app.domain.errors import GroqUnavailableError, SecretNotFoundError
    from app.services.chat.orchestrator import run_chat

    with patch(
        "app.services.chat.orchestrator._load_groq_api_key",
        side_effect=SecretNotFoundError("groq_api_key not found"),
    ):
        with pytest.raises(GroqUnavailableError):
            await run_chat("hello", None, None, None)


# ---------------------------------------------------------------------------
# Orchestrator: no-tool response from injected client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_orchestrator_no_tool_response():
    from app.services.chat.orchestrator import run_chat

    mock_client = AsyncMock()
    mock_client.chat.return_value = {
        "message": {
            "role": "assistant",
            "content": "Here is your answer.",
            "tool_calls": None,
        }
    }

    result = await run_chat("hello", None, None, None, _client=mock_client)

    assert result["answer"] == "Here is your answer."
    assert result["tool_calls"] == []
    assert "conversation_id" in result
    assert "model" in result
    assert "latency_seconds" in result


# ---------------------------------------------------------------------------
# Orchestrator: tool call round-trip with injected client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_orchestrator_executes_rag_query_tool():
    from app.services.chat.orchestrator import run_chat

    first_response = {
        "message": {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_abc",
                    "type": "function",
                    "function": {
                        "name": "rag_query",
                        "arguments": json.dumps({"query": "pod scheduling"}),
                    },
                }
            ],
        }
    }
    second_response = {
        "message": {
            "role": "assistant",
            "content": "Based on the docs, pod scheduling works as follows...",
            "tool_calls": None,
        }
    }

    mock_client = AsyncMock()
    mock_client.chat.side_effect = [first_response, second_response]

    mock_chunk = {"text": "Pod scheduling places pods on nodes.", "source_type": "docs"}
    with patch(
        "app.services.chat.tool_registry.retrieve",
        new=AsyncMock(return_value=([mock_chunk], "hybrid")),
    ):
        result = await run_chat(
            "how does pod scheduling work?", None, None, None, _client=mock_client
        )

    assert "pod scheduling" in result["answer"].lower() or len(result["answer"]) > 0
    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["tool_name"] == "rag_query"
    assert mock_client.chat.call_count == 2


# ---------------------------------------------------------------------------
# Chat schema checks
# ---------------------------------------------------------------------------


def test_chat_request_rejects_empty_message():
    from pydantic import ValidationError

    from app.api.schemas.chat import ChatRequest

    with pytest.raises(ValidationError):
        ChatRequest(message="")


def test_chat_response_shape():
    from app.api.schemas.chat import ChatResponse

    resp = ChatResponse(
        conversation_id="abc123",
        answer="some answer",
        model="llama-3.3-70b-versatile",
        latency_seconds=1.23,
    )
    assert resp.tool_calls == []
    assert resp.trace_id is None


def test_system_prompt_loads():
    from app.services.chat.prompts import load_system_prompt

    prompt = load_system_prompt()
    assert len(prompt) > 50
    assert "Kubernetes" in prompt
