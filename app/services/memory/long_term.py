"""Long-term episodic memory service: store/retrieve in Postgres + audit log.

Every write redacts content and creates an AuditLog row in the same transaction.
No HTTP exceptions. No SQLAlchemy ORM in callers beyond passing repo objects.
"""

from __future__ import annotations

import uuid

from app.domain.memory import LongTermMemoryError
from app.infra.models import AuditLog, Memory
from app.infra.redaction import redact
from app.infra.tracing import get_tracer
from app.repositories.audit_logs import AuditLogRepository
from app.repositories.memories import MemoryRepository
from app.services.memory.config import (
    LONG_TERM_AUDIT_ACTION,
    LONG_TERM_AUDIT_TARGET_TYPE,
    LONG_TERM_LIST_LIMIT,
    LONG_TERM_MEMORY_TYPE,
)


async def store_long_term_memory(
    memory_repo: MemoryRepository,
    audit_repo: AuditLogRepository,
    content: str,
    conversation_id: str = "",
    user_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> dict:
    """Redact, persist an episodic memory, and write an audit log row.

    Raises LongTermMemoryError on any storage failure.
    """
    tracer = get_tracer()

    with tracer.start_span("memory.long_term.write") as span:
        span.set_attribute("memory_type", LONG_TERM_MEMORY_TYPE)
        span.set_attribute("conversation_id", conversation_id or "")

        redacted_content = redact(content)
        span.set_attribute("content_len", str(len(redacted_content)))

        try:
            mem = Memory(
                user_id=user_id,
                conversation_id=conversation_id or None,
                content=redacted_content,
                memory_type=LONG_TERM_MEMORY_TYPE,
                log_metadata=metadata,
            )
            mem = await memory_repo.save(mem)
            memory_id = str(mem.id)

            safe_meta: dict = {"content_len": len(redacted_content)}
            if conversation_id:
                safe_meta["conversation_id"] = conversation_id

            with tracer.start_span("memory.long_term.audit") as audit_span:
                audit_span.set_attribute("action", LONG_TERM_AUDIT_ACTION)
                audit_span.set_attribute("target_id", memory_id)

                audit = AuditLog(
                    actor_user_id=user_id,
                    action=LONG_TERM_AUDIT_ACTION,
                    target_type=LONG_TERM_AUDIT_TARGET_TYPE,
                    target_id=memory_id,
                    log_metadata=safe_meta,
                )
                await audit_repo.save(audit)

            await memory_repo.commit()

        except Exception as exc:
            span.record_exception(exc)
            raise LongTermMemoryError(str(exc)) from exc

        return {
            "status": "stored",
            "memory_id": memory_id,
            "conversation_id": conversation_id,
            "memory_type": LONG_TERM_MEMORY_TYPE,
        }


async def list_long_term_memories(
    memory_repo: MemoryRepository,
    conversation_id: str | None = None,
    user_id: uuid.UUID | None = None,
    limit: int = LONG_TERM_LIST_LIMIT,
) -> list[dict]:
    """List recent episodic memories by conversation_id or user_id."""
    tracer = get_tracer()

    with tracer.start_span("memory.long_term.read") as span:
        span.set_attribute("conversation_id", conversation_id or "")

        if conversation_id:
            memories = await memory_repo.list_by_conversation(
                conversation_id, limit=limit
            )
        elif user_id is not None:
            memories = await memory_repo.list_by_user(user_id, limit=limit)
        else:
            memories = []

        span.set_attribute("item_count", str(len(memories)))
        return [
            {
                "memory_id": str(m.id),
                "content": m.content,
                "memory_type": m.memory_type,
                "conversation_id": m.conversation_id or "",
                "created_at": m.created_at.isoformat() if m.created_at else "",
            }
            for m in memories
        ]


async def store_long_term_memory_with_db(
    content: str,
    conversation_id: str = "",
    user_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> dict:
    """Acquire a DB session and delegate to store_long_term_memory.

    Used by the tool registry so repos are constructed outside the service.
    Raises LongTermMemoryError on any failure.
    """
    from app.infra.db import get_db_session
    from app.repositories.audit_logs import AuditLogRepository as _AuditRepo
    from app.repositories.memories import MemoryRepository as _MemRepo

    gen = get_db_session()
    try:
        session = await gen.__anext__()
        memory_repo = _MemRepo(session)
        audit_repo = _AuditRepo(session)
        return await store_long_term_memory(
            memory_repo, audit_repo, content, conversation_id, user_id, metadata
        )
    finally:
        await gen.aclose()
