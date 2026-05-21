"""HTTP-only layer for /api/v1/rag endpoints.

Routes validate HTTP input, call services, and map domain errors to HTTP status codes.
No business logic lives here.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, status

from app.api.schemas.rag import RagChunkResult, RagQueryRequest, RagQueryResponse
from app.domain.errors import RagCorpusNotReadyError
from app.services.rag.retrieval import retrieve

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])


@router.post("/query", response_model=RagQueryResponse)
async def rag_query(req: RagQueryRequest) -> RagQueryResponse:
    """Retrieve top-k context chunks for a maintainer question.

    Uses E5 hybrid retrieval (alpha=0.7) via the model server.
    Falls back to TF-IDF if the model server is unavailable.
    """
    t0 = time.monotonic()
    try:
        chunks, mode = await retrieve(
            req.question,
            top_k=req.top_k,
            source_type=req.source_type,
            maintainer_only=req.maintainer_only,
        )
    except RagCorpusNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    latency = time.monotonic() - t0

    return RagQueryResponse(
        question=req.question,
        chunks=[
            RagChunkResult(
                chunk_id=c.get("chunk_id", ""),
                text=c.get("text", ""),
                source_type=c.get("source_type", ""),
                score=c.get("score", 0.0),
            )
            for c in chunks
        ],
        retrieval_mode=mode,
        top_k=req.top_k,
        latency_seconds=round(latency, 3),
    )
