"""Schemas for model server endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

IssueLabel = Literal["bug", "feature", "docs", "question"]


class ClassifyRequest(BaseModel):
    title: str = Field(min_length=1)
    body: str = ""


class ClassifyResponse(BaseModel):
    label: IssueLabel
    confidence: float | None
    model: str
    artifact_path: str


class EmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1)
    model: str | None = None


class EmbedResponse(BaseModel):
    embeddings: list[list[float]]
    model: str
    dimension: int
