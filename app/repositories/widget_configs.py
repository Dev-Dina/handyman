from __future__ import annotations

import uuid

from sqlalchemy import select

from app.infra.models import WidgetConfig
from app.repositories.base import BaseRepository


class WidgetConfigRepository(BaseRepository[WidgetConfig]):
    model = WidgetConfig

    async def get_by_public_widget_id(
        self, public_widget_id: uuid.UUID
    ) -> WidgetConfig | None:
        result = await self._session.execute(
            select(WidgetConfig).where(
                WidgetConfig.public_widget_id == public_widget_id
            )
        )
        return result.scalar_one_or_none()

    async def list_by_owner(self, owner_user_id: uuid.UUID) -> list[WidgetConfig]:
        result = await self._session.execute(
            select(WidgetConfig)
            .where(WidgetConfig.owner_user_id == owner_user_id)
            .order_by(WidgetConfig.created_at.desc())
        )
        return list(result.scalars().all())
