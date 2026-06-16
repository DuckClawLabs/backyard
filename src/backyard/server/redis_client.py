"""Shared Redis client."""

from __future__ import annotations

import redis.asyncio as aioredis

from backyard.server.config import settings

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            health_check_interval=30,
            socket_keepalive=True,
            socket_connect_timeout=5,
        )
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
