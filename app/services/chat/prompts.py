"""Load the chat system prompt from the prompts directory."""

from __future__ import annotations

from app.core.paths import PROJECT_ROOT

_SYSTEM_PROMPT_PATH = PROJECT_ROOT / "prompts" / "chat_system.md"

_cached_prompt: str | None = None


def load_system_prompt() -> str:
    """Return the chat system prompt, cached after first read."""
    global _cached_prompt
    if _cached_prompt is None:
        _cached_prompt = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
    return _cached_prompt
