"""Unit tests for app/services/widgets/service.py.

All tests use fake/mock repos. No real DB, no network.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.widgets import (
    WidgetInactiveError,
    WidgetNotFoundError,
    WidgetOriginDeniedError,
)
from app.services.widgets.service import (
    build_csp_frame_ancestors,
    check_origin,
    create_widget,
    get_public_widget,
)

pytestmark = pytest.mark.unit

_PUBLIC_UUID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
_OWNER_UUID = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000002")
_WIDGET_UUID = uuid.UUID("cccccccc-0000-0000-0000-000000000003")


def _make_orm_widget(
    *,
    is_active: bool = True,
    allowed_origins: list | None = None,
    enabled_tools: list | None = None,
) -> MagicMock:
    w = MagicMock()
    w.id = _WIDGET_UUID
    w.public_widget_id = _PUBLIC_UUID
    w.owner_user_id = _OWNER_UUID
    w.allowed_origins = allowed_origins or []
    w.theme = {}
    w.greeting = None
    w.enabled_tools = enabled_tools or []
    w.is_active = is_active
    w.created_at = None
    w.updated_at = None
    return w


# ---------------------------------------------------------------------------
# get_public_widget
# ---------------------------------------------------------------------------


async def test_get_public_widget_returns_dict() -> None:
    repo = MagicMock()
    repo.get_by_public_widget_id = AsyncMock(return_value=_make_orm_widget())
    result = await get_public_widget(repo, _PUBLIC_UUID)
    assert result["public_widget_id"] == _PUBLIC_UUID
    assert result["is_active"] is True


async def test_get_public_widget_raises_not_found() -> None:
    repo = MagicMock()
    repo.get_by_public_widget_id = AsyncMock(return_value=None)
    with pytest.raises(WidgetNotFoundError):
        await get_public_widget(repo, _PUBLIC_UUID)


async def test_get_public_widget_raises_inactive() -> None:
    repo = MagicMock()
    repo.get_by_public_widget_id = AsyncMock(
        return_value=_make_orm_widget(is_active=False)
    )
    with pytest.raises(WidgetInactiveError):
        await get_public_widget(repo, _PUBLIC_UUID)


# ---------------------------------------------------------------------------
# check_origin
# ---------------------------------------------------------------------------


def test_check_origin_allows_when_no_origins() -> None:
    check_origin({"allowed_origins": []}, "https://example.com")


def test_check_origin_allows_matching_origin() -> None:
    check_origin(
        {"allowed_origins": ["https://example.com"]},
        "https://example.com",
    )


def test_check_origin_denies_unknown_origin() -> None:
    with pytest.raises(WidgetOriginDeniedError):
        check_origin(
            {"allowed_origins": ["https://allowed.com"]},
            "https://evil.com",
        )


def test_check_origin_allows_none_origin_header() -> None:
    check_origin({"allowed_origins": ["https://example.com"]}, None)


# ---------------------------------------------------------------------------
# build_csp_frame_ancestors
# ---------------------------------------------------------------------------


def test_build_csp_frame_ancestors_empty_origins() -> None:
    result = build_csp_frame_ancestors({"allowed_origins": []})
    assert result == "frame-ancestors 'self'"


def test_build_csp_frame_ancestors_includes_origins() -> None:
    result = build_csp_frame_ancestors(
        {"allowed_origins": ["https://app.example.com", "https://demo.example.com"]}
    )
    assert "frame-ancestors" in result
    assert "https://app.example.com" in result
    assert "https://demo.example.com" in result


# ---------------------------------------------------------------------------
# create_widget
# ---------------------------------------------------------------------------


async def test_create_widget_returns_public_widget_id() -> None:
    repo = MagicMock()
    saved = _make_orm_widget()
    repo.save = AsyncMock(return_value=saved)
    repo.commit = AsyncMock()
    result = await create_widget(
        repo,
        _OWNER_UUID,
        allowed_origins=[],
        theme={},
        greeting=None,
        enabled_tools=[],
        is_active=True,
    )
    assert "public_widget_id" in result
    assert result["owner_user_id"] == _OWNER_UUID
