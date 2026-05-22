"""Request/response schemas for /api/v1/memory endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class ShortTermMemoryItem(BaseModel):
    role: str
    content: str
    created_at: int
    tool_name: str | None = None
    metadata: dict | None = None


class ShortTermMemoryResponse(BaseModel):
    conversation_id: str
    items: list[ShortTermMemoryItem]


class LongTermMemoryItem(BaseModel):
    memory_id: str
    content: str
    memory_type: str
    conversation_id: str
    created_at: str


class LongTermMemoryResponse(BaseModel):
    items: list[LongTermMemoryItem]
