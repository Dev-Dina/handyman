"""HTTP-only layer for widget config endpoints.

Public:  GET  /api/v1/widgets/{public_widget_id}
Admin:   GET  /api/v1/admin/widgets
         POST /api/v1/admin/widgets
         PATCH /api/v1/admin/widgets/{widget_id}

Validates HTTP inputs, maps domain errors to HTTP codes, calls widget service.
No business logic here. No ORM model imports.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import require_authenticated_user
from app.api.schemas.widgets import (
    WidgetAdminResponse,
    WidgetCreateRequest,
    WidgetPublicResponse,
    WidgetUpdateRequest,
)
from app.domain.auth import ROLE_ADMIN, PermissionDeniedError
from app.domain.widgets import (
    WidgetInactiveError,
    WidgetNotFoundError,
    WidgetOriginDeniedError,
)
from app.infra.db import get_db_session
from app.infra.logging import get_logger
from app.repositories.widget_configs import WidgetConfigRepository
from app.services.auth import require_role
from app.services.widgets.service import (
    build_csp_frame_ancestors,
    check_origin,
    create_widget,
    get_public_widget,
    list_admin_widgets,
    update_widget,
)

router = APIRouter(tags=["widgets"])
logger = get_logger(__name__)


async def _require_admin(
    current_user: dict = Depends(require_authenticated_user),
) -> dict:
    try:
        require_role(current_user, ROLE_ADMIN)
    except PermissionDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


# ---------------------------------------------------------------------------
# Public route
# ---------------------------------------------------------------------------


@router.get(
    "/api/v1/widgets/{public_widget_id}",
    response_model=WidgetPublicResponse,
)
async def get_widget_public(
    public_widget_id: uuid.UUID,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> WidgetPublicResponse:
    repo = WidgetConfigRepository(session)
    try:
        widget = await get_public_widget(repo, public_widget_id)
    except WidgetNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found"
        )
    except WidgetInactiveError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found"
        )

    origin = request.headers.get("origin")
    try:
        check_origin(widget, origin)
    except WidgetOriginDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origin not allowed",
        )

    response.headers["Content-Security-Policy"] = build_csp_frame_ancestors(widget)
    return WidgetPublicResponse(**widget)


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------


@router.get(
    "/api/v1/admin/widgets",
    response_model=list[WidgetAdminResponse],
)
async def list_widgets_admin(
    current_user: dict = Depends(_require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> list[WidgetAdminResponse]:
    repo = WidgetConfigRepository(session)
    owner_id = uuid.UUID(str(current_user["id"]))
    widgets = await list_admin_widgets(repo, owner_id)
    return [WidgetAdminResponse(**w) for w in widgets]


@router.post(
    "/api/v1/admin/widgets",
    response_model=WidgetAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_widget_admin(
    req: WidgetCreateRequest,
    current_user: dict = Depends(_require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> WidgetAdminResponse:
    repo = WidgetConfigRepository(session)
    owner_id = uuid.UUID(str(current_user["id"]))
    try:
        widget = await create_widget(
            repo,
            owner_id,
            allowed_origins=req.allowed_origins,
            theme=req.theme,
            greeting=req.greeting,
            enabled_tools=req.enabled_tools,
            is_active=req.is_active,
        )
    except Exception:
        logger.error("widget.create.unexpected_error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )
    return WidgetAdminResponse(**widget)


@router.patch(
    "/api/v1/admin/widgets/{widget_id}",
    response_model=WidgetAdminResponse,
)
async def update_widget_admin(
    widget_id: uuid.UUID,
    req: WidgetUpdateRequest,
    current_user: dict = Depends(_require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> WidgetAdminResponse:
    repo = WidgetConfigRepository(session)
    updates = req.model_dump(exclude_unset=True)
    try:
        widget = await update_widget(repo, widget_id, updates)
    except WidgetNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found"
        )
    except Exception:
        logger.error("widget.update.unexpected_error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )
    return WidgetAdminResponse(**widget)
