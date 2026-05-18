from __future__ import annotations

from sqlalchemy import select

from app.infra.models import Document
from app.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    model = Document

    async def get_by_hash(self, content_hash: str) -> Document | None:
        result = await self._session.execute(
            select(Document).where(Document.content_hash == content_hash)
        )
        return result.scalar_one_or_none()
