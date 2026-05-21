"""Chat orchestrator: single-LLM tool-calling loop over Groq.

Flow:
  1. Load system prompt.
  2. Call Groq with tools.
  3. Execute any requested tools (up to MAX_TOOL_ROUNDS).
  4. Return final answer + tool call records.

No SQLAlchemy. No HTTPException. No torch. No .venv-gpu.
"""

from __future__ import annotations

import json
import os
import time
import uuid

from app.domain.errors import (
    GroqUnavailableError,
    SecretNotFoundError,
    VaultUnavailableError,
)
from app.infra.groq_client import PRIMARY_MODEL, GroqClient
from app.infra.logging import get_logger, trace_id_var
from app.infra.redaction import redact
from app.infra.tracing import get_tracer
from app.services.chat.prompts import load_system_prompt
from app.services.chat.tool_registry import (
    ALL_TOOL_NAMES,
    TOOL_DEFINITIONS,
    dispatch_tool,
)

MAX_TOOL_ROUNDS: int = 2
DEFAULT_ENABLED_TOOLS: list[str] = ALL_TOOL_NAMES
_MAX_LOG_CHARS: int = 300

logger = get_logger(__name__)


def _load_groq_api_key() -> str:
    """Load the Groq API key from Vault secret/llm path."""
    from app.infra.vault_client import VaultClient

    vault_addr = os.getenv("VAULT_ADDR", "http://localhost:8200")
    vault_token = os.getenv("VAULT_DEV_ROOT_TOKEN", "")
    vc = VaultClient(addr=vault_addr, token=vault_token)
    return vc.get_secret_from_path("llm", "groq_api_key")


def _resolve_tools(enabled_tools: list[str] | None) -> list[str]:
    if enabled_tools is None:
        return DEFAULT_ENABLED_TOOLS
    return [t for t in enabled_tools if t in ALL_TOOL_NAMES]


def _safe_log(value: str) -> str:
    return redact(value[:_MAX_LOG_CHARS])


async def run_chat(
    message: str,
    conversation_id: str | None,
    user_id: str | None,
    enabled_tools: list[str] | None,
    *,
    _client: GroqClient | None = None,
) -> dict:
    """Orchestrate a single chat turn.

    _client: injectable GroqClient for testing; production builds one from Vault.
    Returns a dict compatible with ChatResponse fields.
    Raises GroqUnavailableError if Groq is not configured or unreachable.
    """
    tracer = get_tracer()

    with tracer.start_span("chat.request") as root_span:
        t0 = time.monotonic()
        conv_id = conversation_id or uuid.uuid4().hex

        root_span.set_attribute("conversation_id", conv_id)
        if user_id:
            root_span.set_attribute("user_id", user_id)

        if _client is None:
            try:
                api_key = _load_groq_api_key()
            except (VaultUnavailableError, SecretNotFoundError) as exc:
                raise GroqUnavailableError(
                    f"Groq API key not available: {exc}"
                ) from exc
            _client = GroqClient(api_key=api_key)

        system_prompt = load_system_prompt()
        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ]

        tools_to_use = _resolve_tools(enabled_tools)
        active_tool_defs = [
            t for t in TOOL_DEFINITIONS if t["function"]["name"] in tools_to_use
        ]

        tool_call_records: list[dict] = []
        model_used = PRIMARY_MODEL
        answer = ""

        for round_num in range(MAX_TOOL_ROUNDS + 1):
            with tracer.start_span("llm.groq.chat") as llm_span:
                llm_span.set_attribute("round", str(round_num))
                llm_span.set_attribute("model", model_used)
                llm_span.set_attribute("message_count", str(len(messages)))

                choice = await _client.chat(
                    messages=messages,
                    model=model_used,
                    tools=active_tool_defs if active_tool_defs else None,
                )

            assistant_msg = choice.get("message", {})
            tool_calls = assistant_msg.get("tool_calls") or []

            if not tool_calls or round_num >= MAX_TOOL_ROUNDS:
                answer = (assistant_msg.get("content") or "").strip()
                break

            # Append assistant message with tool_calls to continue the conversation
            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_msg.get("content"),
                    "tool_calls": tool_calls,
                }
            )

            for tc in tool_calls:
                tc_id = tc.get("id", "")
                func = tc.get("function", {})
                tool_name = func.get("name", "")

                raw_args = func.get("arguments", "{}")
                try:
                    args: dict = (
                        json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    )
                except json.JSONDecodeError:
                    args = {}

                logger.info(
                    "chat.tool_call",
                    tool=tool_name,
                    args_preview=_safe_log(str(args)),
                )

                try:
                    result = await dispatch_tool(tool_name, args, tools_to_use)
                    tool_call_records.append(
                        {
                            "tool_name": tool_name,
                            "result": result[:_MAX_LOG_CHARS]
                            if len(result) > _MAX_LOG_CHARS
                            else result,
                            "error": None,
                        }
                    )
                except Exception as exc:
                    result = json.dumps({"error": str(exc)})
                    tool_call_records.append(
                        {
                            "tool_name": tool_name,
                            "result": None,
                            "error": str(exc),
                        }
                    )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": result,
                    }
                )

        latency = time.monotonic() - t0
        trace_id = trace_id_var.get() or None

        root_span.set_attribute("latency_seconds", str(round(latency, 3)))
        root_span.set_attribute("tool_rounds", str(round_num))

        logger.info(
            "chat.complete",
            conversation_id=conv_id,
            tool_count=len(tool_call_records),
            latency=round(latency, 3),
        )

    return {
        "conversation_id": conv_id,
        "answer": answer,
        "tool_calls": tool_call_records,
        "model": model_used,
        "latency_seconds": round(latency, 3),
        "trace_id": trace_id,
    }
