from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _build_url() -> str:
    from app.core.config import get_settings

    s = get_settings()
    pw = s.secret("database_password")
    return f"postgresql+asyncpg://handyman:{pw}@db:5432/handyman"


def get_engine():
    global _engine, _session_factory
    if _engine is None:
        _engine = create_async_engine(_build_url(), pool_pre_ping=True)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    get_engine()
    assert _session_factory is not None
    async with _session_factory() as session:
        yield session
