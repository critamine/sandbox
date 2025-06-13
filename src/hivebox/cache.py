"""Redis caching module."""

import time
import asyncio
from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError
from hivebox.temperature import TemperatureResult

class CacheMessages:
    """Static message strings."""
    REDIS_CONN_FAIL = "Connection to redis server failed"
    REDIS_CONN_SUCCESS = "Connection to redis server succeeded"
    RETRY_TOO_SOON = "Redis reconnect attempted too soon"
    CACHE_OUTDATED = "Cache is outdated"
    CACHE_INVALID = "Cache is invalid or malformed"

class CacheServiceError(Exception):
    """Raised when cache service operations fail."""

class CacheService:
    """Handles temperature data cache updating & retrieval."""

    def __init__(self, dsn: str, redis_config: dict):
        self.dsn = dsn
        self.cfg = redis_config
        self.tag = "temp:latest"
        self.last_retry = None
        self.client = Redis.from_url(self.dsn, **self.cfg)

    async def connect(self) -> None:
        now = int(time.time())
        if self.last_retry is not None:
            delta = now - self.last_retry
            if delta < 300:
                raise CacheServiceError(CacheMessages.RETRY_TOO_SOON)
        self.last_retry = now
        try:
            await self.client.ping()
            print(CacheMessages.REDIS_CONN_SUCCESS, flush=True)
        except RedisError as e:
            raise CacheServiceError(CacheMessages.REDIS_CONN_FAIL) from e

    async def _check(self, cache: TemperatureResult):
        now = int(time.time())
        return (now - cache.timestamp) < 3600

    async def _with_retry(self, op, *args, **kwargs):
        for attempt in (1, 2):
            try:
                return await op(*args, **kwargs)
            except (ConnectionError, RedisError, asyncio.CancelledError) as e:
                if attempt == 1:
                    await self.connect()
                    continue
                raise CacheServiceError(CacheMessages.REDIS_CONN_FAIL) from e
    
    async def fetch(self) -> TemperatureResult:
        raw = await self._with_retry(self.client.get, self.tag)

        try:
            cache = TemperatureResult.model_validate_json(raw)
        except ValidationError:
            raise CacheServiceError(CacheMessages.CACHE_INVALID)

        if await self._check(cache):
            return cache

        raise CacheServiceError(CacheMessages.CACHE_OUTDATED)

    async def update(self, result: TemperatureResult) -> None:
        serialized = result.model_dump_json()
        await self._with_retry(self.client.set, self.tag, serialized)