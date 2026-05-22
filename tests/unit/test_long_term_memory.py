"""Unit tests for long-term episodic memory service."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.domain.memory import LongTermMemoryError
from app.infra.models import AuditLog, Memory
from app.services.memory.config import (
    LONG_TERM_AUDIT_ACTION,
    LONG_TERM_AUDIT_TARGET_TYPE,
    LONG_TERM_MEMORY_TYPE,
)
from app.services.memory.long_term import (
    list_long_term_memories,
    store_long_term_memory,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fake repositories — no real DB required
# ---------------------------------------------------------------------------


@dataclass
class _FakeMemoryRepo:
    _saved: list = field(default_factory=list)
    _committed: bool = False

    async def save(self, obj: Memory) -> Memory:
        if obj.id is None:
            obj.id = uuid.uuid4()
        if obj.created_at is None:
            obj.created_at = datetime.now(timezone.utc)
        self._saved.append(obj)
        return obj

    async def commit(self) -> None:
        self._committed = True

    async def list_by_conversation(
        self, conversation_id: str, limit: int = 50
    ) -> list[Memory]:
        return [m for m in self._saved if m.conversation_id == conversation_id][:limit]

    async def list_by_user(self, user_id: uuid.UUID, limit: int = 50) -> list[Memory]:
        return [m for m in self._saved if m.user_id == user_id][:limit]


@dataclass
class _FakeAuditRepo:
    _saved: list = field(default_factory=list)

    async def save(self, obj: AuditLog) -> AuditLog:
        if obj.id is None:
            obj.id = uuid.uuid4()
        self._saved.append(obj)
        return obj

    async def commit(self) -> None:
        pass


@dataclass
class _RaisingMemoryRepo:
    async def save(self, obj: Memory) -> Memory:
        raise RuntimeError("DB connection refused")

    async def commit(self) -> None:
        pass

    async def list_by_conversation(
        self, conversation_id: str, limit: int = 50
    ) -> list[Memory]:
        return []

    async def list_by_user(self, user_id: uuid.UUID, limit: int = 50) -> list[Memory]:
        return []


# ---------------------------------------------------------------------------
# store_long_term_memory
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_redacts_content() -> None:
    mem_repo = _FakeMemoryRepo()
    audit_repo = _FakeAuditRepo()

    content = "user token is ghp_ABCDEF1234567890ABCDEF1234567890ABCD and needs help"
    await store_long_term_memory(
        mem_repo, audit_repo, content, conversation_id="conv-1"
    )

    assert len(mem_repo._saved) == 1
    stored = mem_repo._saved[0]
    assert "ghp_ABCDEF" not in stored.content
    assert "[REDACTED]" in stored.content


@pytest.mark.asyncio
async def test_store_sets_memory_type_episodic() -> None:
    mem_repo = _FakeMemoryRepo()
    audit_repo = _FakeAuditRepo()

    await store_long_term_memory(
        mem_repo, audit_repo, "a fact", conversation_id="conv-2"
    )

    assert mem_repo._saved[0].memory_type == LONG_TERM_MEMORY_TYPE
    assert LONG_TERM_MEMORY_TYPE == "episodic"


@pytest.mark.asyncio
async def test_store_creates_audit_log_row() -> None:
    mem_repo = _FakeMemoryRepo()
    audit_repo = _FakeAuditRepo()

    result = await store_long_term_memory(
        mem_repo, audit_repo, "fact to audit", conversation_id="conv-3"
    )

    assert len(audit_repo._saved) == 1
    audit = audit_repo._saved[0]
    assert audit.action == LONG_TERM_AUDIT_ACTION
    assert audit.target_type == LONG_TERM_AUDIT_TARGET_TYPE
    assert audit.target_id == result["memory_id"]


@pytest.mark.asyncio
async def test_store_audit_metadata_does_not_contain_raw_content() -> None:
    mem_repo = _FakeMemoryRepo()
    audit_repo = _FakeAuditRepo()

    await store_long_term_memory(
        mem_repo, audit_repo, "secret content abc", conversation_id="conv-4"
    )

    audit = audit_repo._saved[0]
    raw = str(audit.log_metadata)
    assert "secret content abc" not in raw
    assert "content_len" in audit.log_metadata


@pytest.mark.asyncio
async def test_store_commits_transaction() -> None:
    mem_repo = _FakeMemoryRepo()
    audit_repo = _FakeAuditRepo()

    await store_long_term_memory(
        mem_repo, audit_repo, "commit test", conversation_id="conv-5"
    )

    assert mem_repo._committed is True


@pytest.mark.asyncio
async def test_store_returns_structured_result() -> None:
    mem_repo = _FakeMemoryRepo()
    audit_repo = _FakeAuditRepo()

    result = await store_long_term_memory(
        mem_repo, audit_repo, "a fact", conversation_id="conv-6"
    )

    assert result["status"] == "stored"
    assert result["memory_type"] == LONG_TERM_MEMORY_TYPE
    assert result["conversation_id"] == "conv-6"
    assert "memory_id" in result


@pytest.mark.asyncio
async def test_store_raises_long_term_memory_error_on_db_failure() -> None:
    mem_repo = _RaisingMemoryRepo()
    audit_repo = _FakeAuditRepo()

    with pytest.raises(LongTermMemoryError):
        await store_long_term_memory(
            mem_repo, audit_repo, "some fact", conversation_id="conv-fail"
        )


@pytest.mark.asyncio
async def test_store_with_user_id() -> None:
    mem_repo = _FakeMemoryRepo()
    audit_repo = _FakeAuditRepo()
    user_id = uuid.uuid4()

    result = await store_long_term_memory(
        mem_repo,
        audit_repo,
        "user-scoped fact",
        conversation_id="conv-7",
        user_id=user_id,
    )

    stored = mem_repo._saved[0]
    assert stored.user_id == user_id
    audit = audit_repo._saved[0]
    assert audit.actor_user_id == user_id
    assert result["status"] == "stored"


# ---------------------------------------------------------------------------
# list_long_term_memories
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_by_conversation_id() -> None:
    mem_repo = _FakeMemoryRepo()
    audit_repo = _FakeAuditRepo()

    await store_long_term_memory(
        mem_repo, audit_repo, "fact for conv-A", conversation_id="conv-A"
    )
    await store_long_term_memory(
        mem_repo, audit_repo, "fact for conv-B", conversation_id="conv-B"
    )

    results = await list_long_term_memories(mem_repo, conversation_id="conv-A")

    assert len(results) == 1
    assert results[0]["conversation_id"] == "conv-A"


@pytest.mark.asyncio
async def test_list_returns_empty_on_no_match() -> None:
    mem_repo = _FakeMemoryRepo()

    results = await list_long_term_memories(mem_repo, conversation_id="nonexistent")

    assert results == []


@pytest.mark.asyncio
async def test_list_result_shape() -> None:
    mem_repo = _FakeMemoryRepo()
    audit_repo = _FakeAuditRepo()

    await store_long_term_memory(
        mem_repo, audit_repo, "shaped fact", conversation_id="conv-shape"
    )

    results = await list_long_term_memories(mem_repo, conversation_id="conv-shape")

    assert len(results) == 1
    row = results[0]
    assert "memory_id" in row
    assert "content" in row
    assert "memory_type" in row
    assert "conversation_id" in row
    assert "created_at" in row


# ---------------------------------------------------------------------------
# write_memory tool — long_term scope (via dispatch_tool)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_memory_tool_long_term_scope() -> None:
    from app.services.chat.tool_registry import dispatch_tool
    import json

    expected = {
        "status": "stored",
        "memory_id": str(uuid.uuid4()),
        "conversation_id": "conv-lt",
        "memory_type": "episodic",
    }
    with patch(
        "app.services.chat.tool_registry.store_long_term_memory_with_db",
        new=AsyncMock(return_value=expected),
    ):
        result = await dispatch_tool(
            "write_memory",
            {"content": "permanent fact", "scope": "long_term"},
            ["write_memory"],
            conversation_id="conv-lt",
        )

    data = json.loads(result)
    assert data["status"] == "stored"
    assert data["memory_type"] == "episodic"


@pytest.mark.asyncio
async def test_write_memory_tool_long_term_graceful_on_failure() -> None:
    from app.services.chat.tool_registry import dispatch_tool
    import json

    with patch(
        "app.services.chat.tool_registry.store_long_term_memory_with_db",
        new=AsyncMock(side_effect=LongTermMemoryError("DB down")),
    ):
        result = await dispatch_tool(
            "write_memory",
            {"content": "some fact", "scope": "long_term"},
            ["write_memory"],
        )

    data = json.loads(result)
    assert data["status"] == "memory_unavailable"
    assert data["scope"] == "long_term"


@pytest.mark.asyncio
async def test_write_memory_tool_default_scope_is_short_term() -> None:
    """Omitting scope= still routes to short_term Redis path."""
    from app.services.chat.tool_registry import dispatch_tool
    import json
    from unittest.mock import AsyncMock, patch

    expected = {
        "status": "stored",
        "conversation_id": "conv-st",
        "memory_type": "short_term",
        "ttl_seconds": 86400,
    }
    with patch(
        "app.services.chat.tool_registry.store_memory",
        new=AsyncMock(return_value=expected),
    ):
        result = await dispatch_tool(
            "write_memory",
            {"content": "session fact"},
            ["write_memory"],
            conversation_id="conv-st",
        )

    data = json.loads(result)
    assert data["memory_type"] == "short_term"
