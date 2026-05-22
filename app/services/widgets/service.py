"""Widget config service: get, create, update, origin check, CSP header builder.

No HTTP exceptions. No SQLAlchemy in callers beyond passing repo objects.
Raises domain errors only; mapping to HTTP codes happens in the router.
"""

from __future__ import annotations

import uuid

from app.domain.widgets import (
    WidgetInactiveError,
    WidgetNotFoundError,
    WidgetOriginDeniedError,
)
from app.infra.models import WidgetConfig as WidgetConfigORM
from app.infra.tracing import get_tracer
from app.repositories.widget_configs import WidgetConfigRepository
from app.services.widgets.config import (
    CSP_FRAME_ANCESTORS_SELF,
    WIDGET_ADMIN_LIST_LIMIT,
)


def _widget_to_dict(w: WidgetConfigORM) -> dict:
    return {
        "id": w.id,
        "public_widget_id": w.public_widget_id,
        "owner_user_id": w.owner_user_id,
        "allowed_origins": list(w.allowed_origins or []),
        "theme": dict(w.theme or {}),
        "greeting": w.greeting,
        "enabled_tools": list(w.enabled_tools or []),
        "is_active": w.is_active,
        "created_at": w.created_at,
        "updated_at": w.updated_at,
    }


async def get_public_widget(
    repo: WidgetConfigRepository,
    public_widget_id: uuid.UUID,
) -> dict:
    """Fetch an active widget by its public UUID.

    Raises WidgetNotFoundError if no record exists.
    Raises WidgetInactiveError if the widget is disabled.
    """
    tracer = get_tracer()
    with tracer.start_span("widget.get_public") as span:
        span.set_attribute("public_widget_id", str(public_widget_id))
        w = await repo.get_by_public_widget_id(public_widget_id)
        if w is None:
            raise WidgetNotFoundError(str(public_widget_id))
        if not w.is_active:
            raise WidgetInactiveError(str(public_widget_id))
        return _widget_to_dict(w)


def check_origin(widget: dict, origin: str | None) -> None:
    """Raise WidgetOriginDeniedError if origin is rejected by widget policy.

    Policy:
    - No Origin header → allowed (server-to-server or same-origin).
    - Empty allowed_origins list → no restriction enforced.
    - Non-empty allowed_origins → origin must be in the list.
    """
    if origin is None:
        return
    allowed = widget.get("allowed_origins") or []
    if not allowed:
        return
    if origin not in allowed:
        raise WidgetOriginDeniedError(f"Origin not allowed: {origin!r}")


def build_csp_frame_ancestors(widget: dict) -> str:
    """Return the CSP frame-ancestors directive value for this widget.

    Uses allowed_origins when set; falls back to 'self' when empty.
    """
    origins = widget.get("allowed_origins") or []
    if not origins:
        return CSP_FRAME_ANCESTORS_SELF
    return "frame-ancestors " + " ".join(origins)


async def list_admin_widgets(
    repo: WidgetConfigRepository,
    owner_user_id: uuid.UUID,
) -> list[dict]:
    """List all widget configs owned by the given user."""
    tracer = get_tracer()
    with tracer.start_span("widget.list_admin") as span:
        span.set_attribute("owner_user_id", str(owner_user_id))
        widgets = await repo.list_by_owner(owner_user_id)
        span.set_attribute("count", str(len(widgets)))
        return [_widget_to_dict(w) for w in widgets[:WIDGET_ADMIN_LIST_LIMIT]]


async def create_widget(
    repo: WidgetConfigRepository,
    owner_user_id: uuid.UUID,
    *,
    allowed_origins: list[str],
    theme: dict,
    greeting: str | None,
    enabled_tools: list[str],
    is_active: bool,
) -> dict:
    """Create a new widget config owned by owner_user_id."""
    tracer = get_tracer()
    with tracer.start_span("widget.create") as span:
        span.set_attribute("owner_user_id", str(owner_user_id))
        w = WidgetConfigORM(
            owner_user_id=owner_user_id,
            allowed_origins=allowed_origins,
            theme=theme,
            greeting=greeting,
            enabled_tools=enabled_tools,
            is_active=is_active,
        )
        w = await repo.save(w)
        await repo.commit()
        span.set_attribute("widget_id", str(w.id))
        return _widget_to_dict(w)


async def update_widget(
    repo: WidgetConfigRepository,
    widget_id: uuid.UUID,
    updates: dict,
) -> dict:
    """Apply partial updates to a widget config.

    Only keys present in updates are written; absent keys are untouched.
    Raises WidgetNotFoundError if widget_id does not exist.
    """
    tracer = get_tracer()
    with tracer.start_span("widget.update") as span:
        span.set_attribute("widget_id", str(widget_id))
        w = await repo.get_by_id(widget_id)
        if w is None:
            raise WidgetNotFoundError(str(widget_id))
        for key, value in updates.items():
            setattr(w, key, value)
        await repo.save(w)
        await repo.commit()
        return _widget_to_dict(w)
