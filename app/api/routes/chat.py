"""HTTP-only layer for POST /api/v1/chat.

Validates HTTP input, calls the chat orchestrator, maps domain errors to HTTP status codes.
No business logic lives here.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.schemas.chat import ChatRequest, ChatResponse
from app.domain.errors import GroqUnavailableError
from app.infra.logging import get_logger, request_id_var
from app.services.chat.orchestrator import run_chat

router = APIRouter(prefix="/api/v1", tags=["chat"])

logger = get_logger(__name__)


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """Send a message to the tool-calling chatbot and receive an answer.

    Uses Groq llama-3.3-70b-versatile as the primary LLM.
    Available tools: rag_query, extract_entities, summarize, classify_issue, write_memory.
    """
    req_id = request_id_var.get()

    try:
        result = await run_chat(
            message=req.message,
            conversation_id=req.conversation_id,
            user_id=req.user_id,
            enabled_tools=req.enabled_tools,
        )
    except GroqUnavailableError as exc:
        logger.error("chat.groq_unavailable", request_id=req_id, detail=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception:
        logger.error("chat.unexpected_error", request_id=req_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )

    return ChatResponse(**result)
