"""Async Redis adapter for short-term memory storage."""

from __future__ import annotations

import os

import redis.asyncio as aioredis

from app.domain.memory import RedisUnavailableError

_DEFAULT_REDIS_URL: str = "redis://localhost:6379"
_REDIS_URL_ENV: str = "REDIS_URL"


class RedisClient:
    """Thin async wrapper around redis.asyncio.Redis.

    Raises RedisUnavailableError on any connection or command failure.
    """

    def __init__(self, url: str | None = None) -> None:
        self._url = url or os.getenv(_REDIS_URL_ENV, _DEFAULT_REDIS_URL)
        self._redis: aioredis.Redis | None = None

    def _get_client(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(self._url, decode_responses=True)
        return self._redis

    async def rpush(self, key: str, value: str) -> int:
        try:
            return await self._get_client().rpush(key, value)
        except Exception as exc:
            raise RedisUnavailableError(f"Redis rpush failed: {exc}") from exc

    async def ltrim(self, key: str, start: int, end: int) -> None:
        try:
            await self._get_client().ltrim(key, start, end)
        except Exception as exc:
            raise RedisUnavailableError(f"Redis ltrim failed: {exc}") from exc

    async def expire(self, key: str, ttl_seconds: int) -> None:
        try:
            await self._get_client().expire(key, ttl_seconds)
        except Exception as exc:
            raise RedisUnavailableError(f"Redis expire failed: {exc}") from exc

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        try:
            return await self._get_client().lrange(key, start, end)
        except Exception as exc:
            raise RedisUnavailableError(f"Redis lrange failed: {exc}") from exc


_client: RedisClient | None = None


def get_redis_client() -> RedisClient:
    global _client
    if _client is None:
        _client = RedisClient()
    return _client
