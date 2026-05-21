"""Request/response schemas for POST /api/v1/chat."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8192, description="User message")
    conversation_id: str | None = Field(
        None, description="Existing conversation ID to continue"
    )
    user_id: str | None = Field(None, description="Authenticated user ID")
    enabled_tools: list[str] | None = Field(
        None,
        description="Tool whitelist; null means all default tools enabled",
    )


class ToolCallRecord(BaseModel):
    tool_name: str
    result: str | None = None
    error: str | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    tool_calls: list[ToolCallRecord] = []
    model: str
    latency_seconds: float
    trace_id: str | None = None
