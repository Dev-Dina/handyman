from __future__ import annotations

from sqlalchemy import select

from app.infra.models import WidgetConfig
from app.repositories.base import BaseRepository


class WidgetConfigRepository(BaseRepository[WidgetConfig]):
    model = WidgetConfig

    async def get_by_name(self, name: str) -> WidgetConfig | None:
        result = await self._session.execute(
            select(WidgetConfig).where(WidgetConfig.name == name)
        )
        return result.scalar_one_or_none()
