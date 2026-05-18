from __future__ import annotations

import uuid

from sqlalchemy import select

from app.infra.models import Memory
from app.repositories.base import BaseRepository


class MemoryRepository(BaseRepository[Memory]):
    model = Memory

    async def list_by_user(self, user_id: uuid.UUID, limit: int = 50) -> list[Memory]:
        result = await self._session.execute(
            select(Memory)
            .where(Memory.user_id == user_id)
            .order_by(Memory.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
