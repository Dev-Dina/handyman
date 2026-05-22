"""Runtime constants for the short-term memory service."""

from __future__ import annotations

MEMORY_TTL_SECONDS: int = 24 * 60 * 60  # 24 hours — one working day of active context
MEMORY_MAX_ITEMS: int = 50
MEMORY_KEY_PREFIX: str = "memory:short_term"
