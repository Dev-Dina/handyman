"""HTTP-only layer for the /api/v1/tools endpoints.

Routes validate HTTP input, call services, and map domain errors to HTTP status codes.
No business logic lives here.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.schemas.tools import (
    EntityExtractRequest,
    EntityExtractResponse,
    SummarizeRequest,
    SummarizeResponse,
)
from app.domain.errors import OllamaUnavailableError, ToolInputError
from app.services.tools import extract_entities_service, summarize_service

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])


@router.post("/entities", response_model=EntityExtractResponse)
async def entities(req: EntityExtractRequest) -> EntityExtractResponse:
    """Extract Kubernetes entities (versions, commands, components, errors, …) from text."""
    try:
        result = extract_entities_service(req.text)
    except ToolInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    return EntityExtractResponse(**result)


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize(req: SummarizeRequest) -> SummarizeResponse:
    """Summarize issue text into Problem / Expected / Evidence / Component using local Ollama."""
    try:
        result = await summarize_service(req.text, max_chars=req.max_chars)
    except NotImplementedError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)
        )
    except OllamaUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    except ToolInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    return SummarizeResponse(**result)
