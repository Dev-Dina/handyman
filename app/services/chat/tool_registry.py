"""Tool registry: definitions and dispatch for chat tool calls.

All tool results are returned as JSON-serialisable strings so they can be
sent back to the LLM as tool-result messages.
No torch imports. No .venv-gpu. No direct model loading.
"""

from __future__ import annotations

import json

from app.domain.errors import ModelServerUnavailableError, OllamaUnavailableError
from app.domain.memory import (
    MEMORY_SCOPE_LONG,
    MEMORY_SCOPE_SHORT,
    LongTermMemoryError,
    RedisUnavailableError,
)
from app.infra.redis_client import get_redis_client
from app.infra.redaction import redact
from app.infra.tracing import get_tracer
from app.services.memory.long_term import store_long_term_memory_with_db
from app.services.memory.short_term import store_memory
from app.services.rag.retrieval import retrieve
from app.services.tools import extract_entities_service, summarize_service

_MAX_TOOL_OUTPUT_CHARS: int = 4000
_MAX_TOOL_INPUT_TRACE_CHARS: int = 200

DEFAULT_RAG_TOP_K: int = 5

TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "rag_query",
            "description": (
                "Search the Kubernetes knowledge base for relevant documentation "
                "and issue history. Call this before answering questions about "
                "Kubernetes behavior, errors, or past issues."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default 5)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "extract_entities",
            "description": (
                "Extract Kubernetes-specific entities (versions, components, errors, "
                "commands, resources) from issue title/body text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Issue title, body, or other text to analyse",
                    }
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize",
            "description": (
                "Generate a structured summary (Problem / Expected / Evidence / Component) "
                "of an issue or support thread using the local summarisation model."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Issue or thread text to summarise",
                    }
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "classify_issue",
            "description": "Classify a GitHub issue as bug, feature, docs, or question.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Issue title",
                    },
                    "body": {
                        "type": "string",
                        "description": "Issue body text",
                    },
                },
                "required": ["title", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_memory",
            "description": (
                "Save an important fact or user preference for future reference. "
                "Use scope='short_term' (default) for session context or "
                "scope='long_term' for permanent episodic memory."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The fact or preference to remember",
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["short_term", "long_term"],
                        "description": "Storage scope: short_term (Redis, TTL=24h) or long_term (Postgres, permanent)",
                    },
                },
                "required": ["content"],
            },
        },
    },
]

ALL_TOOL_NAMES: list[str] = [t["function"]["name"] for t in TOOL_DEFINITIONS]


def _truncate(text: str, max_chars: int = _MAX_TOOL_OUTPUT_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "...[truncated]"


async def dispatch_tool(
    name: str,
    arguments: dict,
    enabled_tools: list[str],
    *,
    conversation_id: str = "",
) -> str:
    """Execute a tool by name and return a JSON string result.

    If the tool is not enabled, returns a structured error.
    Tool execution exceptions are caught and returned as error payloads
    so the LLM receives informative feedback instead of crashing the request.
    """
    if name not in enabled_tools:
        return json.dumps({"error": "tool_not_enabled", "tool": name})

    tracer = get_tracer()

    if name == "rag_query":
        with tracer.start_span("tool.rag_query") as span:
            query = str(arguments.get("query", ""))
            top_k = int(arguments.get("top_k", DEFAULT_RAG_TOP_K))
            span.set_attribute(
                "query", _truncate(redact(query), _MAX_TOOL_INPUT_TRACE_CHARS)
            )
            try:
                chunks, mode = await retrieve(query, top_k=top_k)
                results = [
                    {
                        "text": _truncate(c.get("text", ""), 800),
                        "source_type": c.get("source_type", ""),
                    }
                    for c in chunks
                ]
                out = json.dumps({"retriever": mode, "results": results})
                span.set_attribute("result_count", str(len(results)))
                return _truncate(out)
            except Exception as exc:
                span.record_exception(exc)
                return json.dumps({"error": str(exc), "tool": "rag_query"})

    if name == "extract_entities":
        with tracer.start_span("tool.extract_entities") as span:
            text = str(arguments.get("text", ""))
            span.set_attribute("text_len", str(len(text)))
            try:
                result = extract_entities_service(text)
                return _truncate(json.dumps(result))
            except Exception as exc:
                span.record_exception(exc)
                return json.dumps({"error": str(exc), "tool": "extract_entities"})

    if name == "summarize":
        with tracer.start_span("tool.summarize") as span:
            text = str(arguments.get("text", ""))
            span.set_attribute("text_len", str(len(text)))
            try:
                result = await summarize_service(text)
                return _truncate(json.dumps(result))
            except OllamaUnavailableError as exc:
                span.record_exception(exc)
                return json.dumps(
                    {"error": "summarize_unavailable", "detail": str(exc)}
                )
            except Exception as exc:
                span.record_exception(exc)
                return json.dumps({"error": str(exc), "tool": "summarize"})

    if name == "classify_issue":
        with tracer.start_span("tool.classify_issue") as span:
            title = str(arguments.get("title", ""))
            body = str(arguments.get("body", ""))
            span.set_attribute(
                "title", _truncate(redact(title), _MAX_TOOL_INPUT_TRACE_CHARS)
            )
            try:
                from app.infra.modelserver_client import ModelServerClient

                client = ModelServerClient()
                result = await client.classify(title=title, body=body)
                return json.dumps(result)
            except ModelServerUnavailableError:
                return json.dumps(
                    {
                        "status": "tool_unavailable",
                        "tool": "classify_issue",
                        "reason": "model_server_not_ready",
                    }
                )
            except Exception as exc:
                span.record_exception(exc)
                return json.dumps({"error": str(exc), "tool": "classify_issue"})

    if name == "write_memory":
        with tracer.start_span("tool.write_memory") as span:
            content = str(arguments.get("content", ""))
            scope = str(arguments.get("scope", MEMORY_SCOPE_SHORT))
            span.set_attribute("content_len", str(len(content)))
            span.set_attribute("conversation_id", conversation_id)
            span.set_attribute("scope", scope)

            if scope == MEMORY_SCOPE_LONG:
                try:
                    result = await store_long_term_memory_with_db(
                        content=content,
                        conversation_id=conversation_id,
                    )
                    return json.dumps(result)
                except LongTermMemoryError as exc:
                    span.record_exception(exc)
                    return json.dumps(
                        {
                            "status": "memory_unavailable",
                            "scope": "long_term",
                            "reason": "Postgres not reachable",
                        }
                    )
                except Exception as exc:
                    span.record_exception(exc)
                    return json.dumps({"error": str(exc), "tool": "write_memory"})
            else:
                try:
                    result = await store_memory(
                        redis_client=get_redis_client(),
                        conversation_id=conversation_id,
                        content=content,
                    )
                    return json.dumps(result)
                except RedisUnavailableError as exc:
                    span.record_exception(exc)
                    return json.dumps(
                        {
                            "status": "memory_unavailable",
                            "reason": "Redis not reachable",
                        }
                    )
                except Exception as exc:
                    span.record_exception(exc)
                    return json.dumps({"error": str(exc), "tool": "write_memory"})

    return json.dumps({"error": "unknown_tool", "tool": name})
