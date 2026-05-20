"""Request/response schemas for the /api/v1/tools endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EntityExtractRequest(BaseModel):
    text: str = Field(
        ..., min_length=1, description="Text to extract Kubernetes entities from"
    )


class EntityExtractResponse(BaseModel):
    entities_by_type: dict[str, list[str]]
    total_count: int


class SummarizeRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text to summarize")
    max_chars: int | None = Field(
        None, gt=0, description="Optional character limit for the summary"
    )


class SummarizeResponse(BaseModel):
    summary: str
    model: str
    latency_seconds: float
