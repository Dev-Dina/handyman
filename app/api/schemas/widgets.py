"""Request/response schemas for /api/v1/widgets and /api/v1/admin/widgets."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class WidgetPublicResponse(BaseModel):
    public_widget_id: uuid.UUID
    theme: dict[str, Any]
    greeting: str | None
    enabled_tools: list[str]
    is_active: bool


class WidgetAdminResponse(BaseModel):
    id: uuid.UUID
    public_widget_id: uuid.UUID
    owner_user_id: uuid.UUID
    allowed_origins: list[str]
    theme: dict[str, Any]
    greeting: str | None
    enabled_tools: list[str]
    is_active: bool
    created_at: datetime | None = None


def _validate_origins(v: list[str]) -> list[str]:
    for origin in v:
        if not (origin.startswith("http://") or origin.startswith("https://")):
            raise ValueError(f"origin must start with http:// or https://: {origin!r}")
    return v


class WidgetCreateRequest(BaseModel):
    allowed_origins: list[str] = Field(default_factory=list)
    theme: dict[str, Any] = Field(default_factory=dict)
    greeting: str | None = None
    enabled_tools: list[str] = Field(default_factory=list)
    is_active: bool = True

    @field_validator("allowed_origins")
    @classmethod
    def validate_origins(cls, v: list[str]) -> list[str]:
        return _validate_origins(v)


class WidgetUpdateRequest(BaseModel):
    allowed_origins: list[str] | None = None
    theme: dict[str, Any] | None = None
    greeting: str | None = None
    enabled_tools: list[str] | None = None
    is_active: bool | None = None

    @field_validator("allowed_origins")
    @classmethod
    def validate_origins(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        return _validate_origins(v)
