"""HTTP-only layer for /api/v1/rag endpoints.

Routes validate HTTP input, call services, and map domain errors to HTTP status codes.
No business logic lives here.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, status

from app.api.schemas.rag import RagChunkResult, RagQueryRequest, RagQueryResponse
from app.domain.errors import RagCorpusNotReadyError
from app.infra.logging import get_logger, request_id_var
from app.infra.redaction import redact
from app.infra.tracing import get_tracer
from app.services.rag.config import HYBRID_ALPHA
from app.services.rag.retrieval import build_extractive_answer, retrieve

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])

logger = get_logger(__name__)

_RETRIEVER_TO_ALPHA: dict[str, float] = {
    "tfidf": 0.0,
    "hybrid": HYBRID_ALPHA,
    "auto": HYBRID_ALPHA,
}


@router.post("/query", response_model=RagQueryResponse)
async def rag_query(req: RagQueryRequest) -> RagQueryResponse:
    """Retrieve top-k context chunks for a maintainer question.

    Uses E5 hybrid retrieval (alpha=0.7) via the model server by default.
    Falls back to TF-IDF if the model server is unavailable.
    """
    t0 = time.monotonic()
    req_id = request_id_var.get()
    alpha = _RETRIEVER_TO_ALPHA.get(req.retriever, HYBRID_ALPHA)

    tracer = get_tracer()
    with tracer.start_span("rag.query") as span:
        span.set_attribute("top_k", str(req.top_k))
        span.set_attribute("retriever", req.retriever)
        span.set_attribute("query_transform", req.query_transform)
        if req.source_type:
            span.set_attribute("source_type", req.source_type)
        span.set_attribute("maintainer_only", str(req.maintainer_only))

        try:
            chunks, mode = await retrieve(
                req.question,
                top_k=req.top_k,
                source_type=req.source_type,
                maintainer_only=req.maintainer_only,
                query_transform=req.query_transform,
                alpha=alpha,
            )
        except RagCorpusNotReadyError as exc:
            logger.error("rag.corpus_not_ready", request_id=req_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            )
        except Exception as exc:
            logger.error(
                "rag.query.unexpected_error",
                request_id=req_id,
                exc_type=type(exc).__name__,
                exc_msg=redact(str(exc)),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred.",
            )

        span.set_attribute("retriever_used", mode)
        span.set_attribute("returned_count", str(len(chunks)))

    latency = time.monotonic() - t0

    return RagQueryResponse(
        question=req.question,
        retriever_used=mode,
        query_transform_used=req.query_transform,
        top_k=req.top_k,
        results=[
            RagChunkResult(
                chunk_id=c.get("chunk_id", ""),
                text=c.get("text", ""),
                source_type=c.get("source_type", ""),
                score=c.get("score", 0.0),
            )
            for c in chunks
        ],
        answer=build_extractive_answer(chunks),
        latency_seconds=round(latency, 3),
    )
