"""Redis client and a fixed-window rate limiter."""

import time

from redis.asyncio import Redis

from app.core.config import get_settings

_client: Redis | None = None


def get_redis() -> Redis:
    global _client
    if _client is None:
        _client = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return _client


def set_redis(client: Redis | None) -> None:
    """Swap the client (tests use fakeredis)."""
    global _client
    _client = client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
    _client = None


async def hit_rate_limit(
    redis: Redis, key: str, limit: int, window_s: int = 60
) -> tuple[bool, int]:
    """Count a request. Returns (allowed, remaining)."""
    bucket = int(time.time() // window_s)
    redis_key = f"rl:{key}:{bucket}"
    async with redis.pipeline(transaction=True) as pipe:
        pipe.incr(redis_key)
        pipe.expire(redis_key, window_s + 1)
        count, _ = await pipe.execute()
    return count <= limit, max(limit - int(count), 0)
