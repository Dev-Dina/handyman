"""Domain errors and constants for the chat subsystem."""

from __future__ import annotations

from app.domain.errors import GroqUnavailableError  # re-export for chat callers

__all__ = ["GroqUnavailableError"]
