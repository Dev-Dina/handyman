"""Request/response schemas for POST /api/v1/rag/query."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RagQueryRequest(BaseModel):
    question: str = Field(
        ..., min_length=1, description="Maintainer question to retrieve context for"
    )
    top_k: int = Field(5, ge=1, le=20, description="Number of chunks to return")
    source_type: str | None = Field(
        None, description="Optional filter: docs, issue, or comment"
    )
    maintainer_only: bool = Field(
        False, description="If true, restrict to maintainer-authored chunks"
    )
    retriever: str = Field(
        "auto",
        description="Retrieval mode: 'tfidf' (CI-safe, no modelserver), "
        "'hybrid' (E5 + TF-IDF, requires modelserver), "
        "'auto' (hybrid with TF-IDF fallback)",
    )
    query_transform: str = Field(
        "none",
        description="Query transform to apply before retrieval: 'none' or 'technical_terms'",
    )


class RagChunkResult(BaseModel):
    chunk_id: str
    text: str
    source_type: str
    score: float


class RagQueryResponse(BaseModel):
    question: str
    retriever_used: str
    query_transform_used: str
    top_k: int
    results: list[RagChunkResult]
    answer: str | None
    latency_seconds: float
