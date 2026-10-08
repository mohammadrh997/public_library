import json
import logging
from typing import Annotated, Any

import redis.asyncio as redis
from fastapi import Depends, Request
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

BOOK_LIST_PREFIX = "books:list:"
BOOK_LIST_TTL_SECONDS = 60


def create_redis_client(url: str) -> redis.Redis:
    return redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=0.5,
        socket_timeout=0.5,
    )


async def get_cache(request: Request) -> redis.Redis | None:
    return getattr(request.app.state, "redis", None)


Cache = Annotated[redis.Redis | None, Depends(get_cache)]


def book_list_key(skip: int, limit: int, author: str | None) -> str:
    return f"{BOOK_LIST_PREFIX}skip={skip}:limit={limit}:author={author or ''}"


async def cache_get(cache: redis.Redis | None, key: str) -> Any | None:
    if cache is None:
        return None
    try:
        raw = await cache.get(key)
    except RedisError:
        logger.warning("Cache read failed for %s, using the database", key)
        return None
    return json.loads(raw) if raw is not None else None


async def cache_set(cache: redis.Redis | None, key: str, value: Any, ttl: int) -> None:
    if cache is None:
        return
    try:
        await cache.set(key, json.dumps(value), ex=ttl)
    except RedisError:
        logger.warning("Cache write failed for %s, continuing without caching", key)


async def invalidate_book_lists(cache: redis.Redis | None) -> None:
    if cache is None:
        return
    try:
        async for key in cache.scan_iter(match=f"{BOOK_LIST_PREFIX}*"):
            await cache.delete(key)
    except RedisError:
        logger.warning("Cache invalidation failed; stale lists expire within their TTL")
