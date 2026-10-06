"""Redis helpers. Everything fails open: if Redis is down the app keeps serving from Postgres."""

import json
import logging
from typing import Any

from redis import asyncio as aioredis
from redis.exceptions import RedisError

from app.config import Settings
from app.observability import CACHE_REQUESTS, REDIS_ERRORS

log = logging.getLogger(__name__)

CATALOG_KEY = "catalog:v1"


def create_redis(settings: Settings) -> aioredis.Redis:
    password = settings.redis_password.get_secret_value() if settings.redis_password else None
    kwargs: dict[str, Any] = {}
    if settings.redis_tls:
        kwargs |= {"ssl": True, "ssl_ca_certs": settings.redis_ca_cert}
    return aioredis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=password,
        decode_responses=True,
        socket_timeout=settings.redis_timeout_seconds,
        socket_connect_timeout=settings.redis_timeout_seconds,
        health_check_interval=30,
        **kwargs,
    )


class Cache:
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    def _failed(self, op: str, exc: Exception) -> None:
        REDIS_ERRORS.labels(op=op).inc()
        log.warning("redis %s failed, continuing without cache: %s", op, exc)

    async def get_json(self, key: str) -> Any | None:
        try:
            raw = await self.redis.get(key)
        except RedisError as exc:
            self._failed("get", exc)
            CACHE_REQUESTS.labels(result="error").inc()
            return None
        CACHE_REQUESTS.labels(result="hit" if raw is not None else "miss").inc()
        return json.loads(raw) if raw is not None else None

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        try:
            await self.redis.set(key, json.dumps(value, default=str), ex=ttl_seconds)
        except RedisError as exc:
            self._failed("set", exc)

    async def delete(self, *keys: str) -> None:
        try:
            await self.redis.delete(*keys)
        except RedisError as exc:
            self._failed("delete", exc)

    async def incr(self, key: str) -> int | None:
        try:
            return await self.redis.incr(key)
        except RedisError as exc:
            self._failed("incr", exc)
            return None

    async def get_counts(self, keys: list[str]) -> list[int]:
        if not keys:
            return []
        try:
            values = await self.redis.mget(keys)
        except RedisError as exc:
            self._failed("mget", exc)
            return [0] * len(keys)
        return [int(v) if v else 0 for v in values]

    async def is_rate_limited(self, key: str, limit: int, window_seconds: int) -> bool:
        """Fixed-window counter. Fails open so a Redis outage doesn't lock everyone out."""
        try:
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.incr(key)
                pipe.expire(key, window_seconds, nx=True)
                count, _ = await pipe.execute()
        except RedisError as exc:
            self._failed("rate_limit", exc)
            return False
        return count > limit

    async def ping(self) -> bool:
        try:
            return bool(await self.redis.ping())
        except RedisError:
            return False


def views_key(video_id: object) -> str:
    return f"views:{video_id}"
