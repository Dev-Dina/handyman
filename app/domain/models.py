from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UserDomain(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    email: str
    role: str = "user"
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WidgetConfigDomain(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    public_widget_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    owner_user_id: uuid.UUID
    allowed_origins: list[str] = Field(default_factory=list)
    theme: dict[str, Any] = Field(default_factory=dict)
    greeting: str | None = None
    enabled_tools: list[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ConversationDomain(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: uuid.UUID | None = None
    widget_id: uuid.UUID | None = None
    title: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MessageDomain(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    conversation_id: uuid.UUID
    role: str
    content: str
    created_at: datetime | None = None


class MemoryDomain(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: uuid.UUID
    content: str
    embedding: list[float] | None = None
    created_at: datetime | None = None


class AuditLogDomain(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    actor_user_id: uuid.UUID | None = None
    action: str
    target_type: str
    target_id: str | None = None
    log_metadata: dict[str, Any] | None = None
    created_at: datetime | None = None


class DocumentDomain(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    title: str
    source_url: str | None = None
    content_hash: str
    created_at: datetime | None = None


class ChunkDomain(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    document_id: uuid.UUID
    content: str
    embedding: list[float] | None = None
    chunk_index: int
    created_at: datetime | None = None
