"""Runtime constants for the widget config service."""

from __future__ import annotations

VALID_TOOLS: tuple[str, ...] = (
    "rag_query",
    "extract_entities",
    "summarize",
    "classify_issue",
    "write_memory",
)

CSP_FRAME_ANCESTORS_SELF: str = "frame-ancestors 'self'"

WIDGET_ADMIN_LIST_LIMIT: int = 100
