"""Summarization service using Ollama local LLM.

Produces a structured four-part summary of a Kubernetes issue or support thread:
  Problem / Expected / Evidence / Component
"""

from __future__ import annotations

import time

from app.infra.ollama_client import DEFAULT_MODEL, DEFAULT_TIMEOUT_SECONDS, OllamaClient

_MAX_INPUT_CHARS: int = 6000

_SYSTEM_PROMPT: str = (
    "You are a Kubernetes maintainer assistant. "
    "Summarize the following issue or support thread concisely.\n\n"
    "Your summary must cover exactly these four points:\n"
    "1. Problem — what is broken, failing, or being requested\n"
    "2. Expected — what behavior the reporter expected\n"
    "3. Evidence — key technical details: versions, error messages, commands, logs\n"
    "4. Component — the likely Kubernetes component or subsystem involved "
    "(write 'unknown' if not inferable)\n\n"
    "Rules:\n"
    "- Be concise — one or two sentences per point.\n"
    "- Do not repeat the issue title verbatim.\n"
    "- Do not add greetings, disclaimers, or filler text.\n"
    "- Respond only with the four labeled points."
)


def _truncate_input(text: str) -> str:
    if len(text) <= _MAX_INPUT_CHARS:
        return text
    return text[:_MAX_INPUT_CHARS].rstrip() + "\n[truncated]"


def _truncate_summary(summary: str, max_chars: int) -> str:
    if len(summary) <= max_chars:
        return summary
    cut = summary[:max_chars].rstrip()
    last_period = cut.rfind(".")
    if last_period > max_chars // 2:
        return cut[: last_period + 1]
    return cut + "…"


async def summarize(
    text: str,
    *,
    max_chars: int | None = None,
    model: str = DEFAULT_MODEL,
    base_url: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict:
    """Summarize text via Ollama and return {summary, model, latency_seconds}.

    Raises OllamaUnavailableError if Ollama cannot be reached.
    """
    client_kwargs: dict = {"timeout": timeout}
    if base_url is not None:
        client_kwargs["base_url"] = base_url
    client = OllamaClient(**client_kwargs)

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _truncate_input(text)},
    ]

    t0 = time.monotonic()
    raw = await client.chat(model=model, messages=messages)
    latency = time.monotonic() - t0

    summary = raw.strip()
    if max_chars is not None:
        summary = _truncate_summary(summary, max_chars)

    return {
        "summary": summary,
        "model": model,
        "latency_seconds": round(latency, 3),
    }
