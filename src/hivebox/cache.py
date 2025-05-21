"""Redis caching module."""

import json
import time
from redis.asyncio import Redis
from redis.exceptions import ConnectionError
from hivebox.temperature import TemperatureResult

class CacheMessages:
    REDIS_CONN_FAIL = "Connection to redis server failed"
    REDIS_CONN_SUCCESS = "Connection to redis server succeeded"
    RETRY_TOO_SOON = "Tried to reconnect too soon"
    CACHE_OUTDATED = "Cache is outdated"

class CacheServiceError(Exception):
    """Raised when cache service operations fail."""

class CacheService:
    """Handles temperature data caching and retrieval."""

    def __init__(self, dsn: str, redis_config: dict):
        self.dsn = dsn
        self.cfg = redis_config
        self.tag = "temp:latest"
        self.client = None
        self.last_retry = None

    async def connect(self):
        now = int(time.time())
        if self.last_retry is not None:
            delta = now - self.last_retry
            if delta < 300:
                raise CacheServiceError(CacheMessages.RETRY_TOO_SOON)
        self.last_retry = now
        self.client = await Redis.from_url(self.dsn, **self.cfg)
        try:
            await self.client.ping()
            print(CacheMessages.REDIS_CONN_SUCCESS, flush=True)
        except ConnectionError:
            print(CacheMessages.REDIS_CONN_FAIL, flush=True)

    async def _check(self, cache: TemperatureResult):
        now = int(time.time())
        return (now - cache.timestamp) < 3600

    async def fetch(self):
        try:
            raw = await self.client.get(self.tag)
        except ConnectionError:
            await self.connect()
            raw = await self.client.get(self.tag)
        cache = TemperatureResult.model_validate_json(raw)
        if await self._check(cache):
            return cache
        else:
            raise CacheServiceError(CacheMessages.CACHE_OUTDATED)

    async def update(self, result: TemperatureResult):
        serialized = result.model_dump_json()
        try:
            await self.client.set(self.tag, serialized)
        except ConnectionError:
            await self.connect()
            await self.client.set(self.tag, serialized)