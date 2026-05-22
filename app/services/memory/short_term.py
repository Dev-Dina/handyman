"""Short-term memory service: store and retrieve conversation context in Redis."""

from __future__ import annotations

import json
import time

from app.domain.memory import MEMORY_ROLE_MEMORY, RedisUnavailableError
from app.infra.redis_client import RedisClient
from app.infra.redaction import redact
from app.infra.tracing import get_tracer
from app.services.memory.config import (
    MEMORY_KEY_PREFIX,
    MEMORY_MAX_ITEMS,
    MEMORY_TTL_SECONDS,
)


def _make_key(conversation_id: str) -> str:
    safe_id = conversation_id.replace(":", "_") if conversation_id else "default"
    return f"{MEMORY_KEY_PREFIX}:{safe_id}"


async def store_memory(
    redis_client: RedisClient,
    conversation_id: str,
    content: str,
    *,
    role: str = MEMORY_ROLE_MEMORY,
    tool_name: str | None = None,
    metadata: dict | None = None,
) -> dict:
    """Store a redacted memory item in Redis with TTL.

    Raises RedisUnavailableError if the Redis connection fails.
    """
    tracer = get_tracer()

    with tracer.start_span("memory.short_term.write") as span:
        span.set_attribute("conversation_id", conversation_id or "")
        span.set_attribute("role", role)

        redacted_content = redact(content)

        item: dict = {
            "role": role,
            "content": redacted_content,
            "created_at": int(time.time()),
        }
        if tool_name is not None:
            item["tool_name"] = tool_name
        if metadata is not None:
            item["metadata"] = metadata

        key = _make_key(conversation_id)
        serialized = json.dumps(item)

        try:
            await redis_client.rpush(key, serialized)
            await redis_client.ltrim(key, -MEMORY_MAX_ITEMS, -1)
            await redis_client.expire(key, MEMORY_TTL_SECONDS)
        except RedisUnavailableError:
            with tracer.start_span("memory.short_term.unavailable") as err_span:
                err_span.set_attribute("conversation_id", conversation_id or "")
            raise

        span.set_attribute("content_len", str(len(redacted_content)))
        span.set_attribute("ttl_seconds", str(MEMORY_TTL_SECONDS))

        return {
            "status": "stored",
            "conversation_id": conversation_id,
            "memory_type": "short_term",
            "ttl_seconds": MEMORY_TTL_SECONDS,
        }


async def read_memory(
    redis_client: RedisClient,
    conversation_id: str,
    *,
    limit: int = MEMORY_MAX_ITEMS,
) -> list[dict]:
    """Read recent memory items for a conversation.

    Returns empty list if Redis is unavailable (graceful degradation).
    """
    tracer = get_tracer()

    with tracer.start_span("memory.short_term.read") as span:
        span.set_attribute("conversation_id", conversation_id or "")
        key = _make_key(conversation_id)

        try:
            raw_items = await redis_client.lrange(key, -limit, -1)
        except RedisUnavailableError:
            with tracer.start_span("memory.short_term.unavailable"):
                pass
            return []

        items: list[dict] = []
        for raw in raw_items:
            try:
                items.append(json.loads(raw))
            except json.JSONDecodeError:
                continue

        span.set_attribute("item_count", str(len(items)))
        return items
