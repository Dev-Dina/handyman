"""HTTP-only layer for /api/v1/memory endpoints.

Read-only access to short-term (Redis) and long-term (Postgres) memory
for authenticated users. Writes happen only through the write_memory tool.
No business logic here — delegates to memory services.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import require_authenticated_user
from app.api.schemas.memory import LongTermMemoryResponse, ShortTermMemoryResponse
from app.domain.memory import RedisUnavailableError
from app.infra.db import get_db_session
from app.infra.logging import get_logger
from app.infra.redis_client import get_redis_client
from app.repositories.memories import MemoryRepository
from app.services.memory.long_term import list_long_term_memories
from app.services.memory.short_term import read_memory

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])
logger = get_logger(__name__)


@router.get("/short-term", response_model=ShortTermMemoryResponse)
async def get_short_term_memory(
    conversation_id: str,
    current_user: dict = Depends(require_authenticated_user),
) -> ShortTermMemoryResponse:
    redis_client = get_redis_client()
    try:
        items = await read_memory(redis_client, conversation_id)
    except RedisUnavailableError:
        logger.warning("memory.short_term.unavailable", conversation_id=conversation_id)
        items = []
    return ShortTermMemoryResponse(conversation_id=conversation_id, items=items)


@router.get("/long-term", response_model=LongTermMemoryResponse)
async def get_long_term_memories_route(
    conversation_id: str | None = None,
    current_user: dict = Depends(require_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> LongTermMemoryResponse:
    try:
        user_id: uuid.UUID = uuid.UUID(str(current_user["id"]))
    except (KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identity in token",
        )
    memory_repo = MemoryRepository(session)
    memories = await list_long_term_memories(
        memory_repo,
        conversation_id=conversation_id,
        user_id=user_id if not conversation_id else None,
    )
    return LongTermMemoryResponse(items=memories)
