"""Unit tests for short-term Redis memory service."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from app.domain.memory import RedisUnavailableError
from app.services.memory.config import MEMORY_MAX_ITEMS, MEMORY_TTL_SECONDS
from app.services.memory.short_term import read_memory, store_memory

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fake Redis client — no real Redis required
# ---------------------------------------------------------------------------


@dataclass
class _FakeRedisClient:
    _lists: dict = field(default_factory=dict)
    expire_calls: list = field(default_factory=list)
    ltrim_calls: list = field(default_factory=list)

    async def rpush(self, key: str, value: str) -> int:
        self._lists.setdefault(key, []).append(value)
        return len(self._lists[key])

    async def ltrim(self, key: str, start: int, end: int) -> None:
        self.ltrim_calls.append((key, start, end))
        items = self._lists.get(key, [])
        if start < 0:
            start = max(0, len(items) + start)
        if end < 0:
            end = len(items) + end
        self._lists[key] = items[start : end + 1]

    async def expire(self, key: str, ttl_seconds: int) -> None:
        self.expire_calls.append((key, ttl_seconds))

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        items = self._lists.get(key, [])
        if start < 0:
            start = max(0, len(items) + start)
        if end < 0:
            end = len(items) + end
        return items[start : end + 1]


@dataclass
class _FailingRedisClient:
    async def rpush(self, key: str, value: str) -> int:
        raise RedisUnavailableError("connection refused")

    async def ltrim(self, key: str, start: int, end: int) -> None:
        raise RedisUnavailableError("connection refused")

    async def expire(self, key: str, ttl_seconds: int) -> None:
        raise RedisUnavailableError("connection refused")

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        raise RedisUnavailableError("connection refused")


# ---------------------------------------------------------------------------
# store_memory tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_memory_redacts_api_key() -> None:
    client = _FakeRedisClient()
    content = "user said their token is sk-abc1234567890123456 and needs help"

    await store_memory(client, "conv-1", content)

    items = client._lists.get("memory:short_term:conv-1", [])
    assert len(items) == 1
    stored = json.loads(items[0])
    assert "sk-abc1234567890123456" not in stored["content"]
    assert "[REDACTED]" in stored["content"]


@pytest.mark.asyncio
async def test_store_memory_sets_ttl() -> None:
    client = _FakeRedisClient()

    await store_memory(client, "conv-ttl", "some fact")

    assert len(client.expire_calls) == 1
    key, ttl = client.expire_calls[0]
    assert key == "memory:short_term:conv-ttl"
    assert ttl == MEMORY_TTL_SECONDS
    assert ttl == 86400


@pytest.mark.asyncio
async def test_store_memory_enforces_max_items() -> None:
    client = _FakeRedisClient()

    await store_memory(client, "conv-trim", "a fact")

    assert len(client.ltrim_calls) == 1
    key, start, end = client.ltrim_calls[0]
    assert key == "memory:short_term:conv-trim"
    assert start == -MEMORY_MAX_ITEMS
    assert end == -1


@pytest.mark.asyncio
async def test_store_memory_returns_structured_result() -> None:
    client = _FakeRedisClient()

    result = await store_memory(client, "conv-ret", "a fact")

    assert result["status"] == "stored"
    assert result["conversation_id"] == "conv-ret"
    assert result["memory_type"] == "short_term"
    assert result["ttl_seconds"] == MEMORY_TTL_SECONDS


@pytest.mark.asyncio
async def test_store_memory_raises_on_redis_unavailable() -> None:
    client = _FailingRedisClient()

    with pytest.raises(RedisUnavailableError):
        await store_memory(client, "conv-fail", "a fact")


@pytest.mark.asyncio
async def test_read_memory_returns_stored_items() -> None:
    client = _FakeRedisClient()
    await store_memory(client, "conv-read", "pods use namespace isolation")

    items = await read_memory(client, "conv-read")

    assert len(items) == 1
    assert items[0]["role"] == "memory"
    assert "pods use namespace isolation" in items[0]["content"]
    assert "created_at" in items[0]


@pytest.mark.asyncio
async def test_read_memory_graceful_on_unavailable() -> None:
    client = _FailingRedisClient()

    items = await read_memory(client, "conv-down")

    assert items == []


@pytest.mark.asyncio
async def test_store_memory_includes_optional_tool_name() -> None:
    client = _FakeRedisClient()

    await store_memory(
        client, "conv-tool", "entity result", tool_name="extract_entities"
    )

    raw = client._lists["memory:short_term:conv-tool"][0]
    stored = json.loads(raw)
    assert stored["tool_name"] == "extract_entities"
