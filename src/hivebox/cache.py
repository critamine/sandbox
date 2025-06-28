"""Redis caching module (refactored)."""

import time
import asyncio
from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError
from hivebox.metrics import REDIS_CALLS
from hivebox.temperature import TemperatureResult

class CacheMessages:
    """Static message strings for cache operations."""
    REDIS_CONN_FAIL = "Connection to redis server failed"
    REDIS_CONN_SUCCESS = "Connection to redis server succeeded"
    RETRY_TOO_SOON = "Redis reconnect attempted too soon"
    CACHE_OUTDATED = "Cache is outdated"
    CACHE_INVALID = "Cache is invalid or malformed"

class CacheServiceError(Exception):
    """Raised when cache service operations fail."""

class CacheService:
    """Handles temperature-data cache updating & retrieval."""

    def __init__(self, dsn: str, redis_config: dict):
        self.dsn = dsn
        self.cfg = redis_config
        self.tag = "temp:latest"
        self.last_retry = None
        self.client: Redis | None = None

    async def _redis_call(
        self,
        redis_method,
        *args,
        mode: str,
        operation: str,
        **kwargs,
    ):
        """Central wrapper for Redis calls, adding retry on failure and incrementing metrics."""
        for attempt in (1, 2):
            try:
                result = await redis_method(*args, **kwargs)
                REDIS_CALLS.labels(mode=mode, operation=operation, result="success").inc()
                return result
            except (ConnectionError, RedisError, asyncio.CancelledError) as e:
                REDIS_CALLS.labels(mode=mode, operation=operation, result="error").inc()
                if attempt == 1:
                    await self.connect()  # one reconnect try
                    continue
                raise CacheServiceError(CacheMessages.REDIS_CONN_FAIL) from e

    async def connect(self) -> None:
        """(Re)initialise the Redis client, counted as a 'connect' operation."""
        now = int(time.time())
        if self.last_retry and (now - self.last_retry) < 300:
            raise CacheServiceError(CacheMessages.RETRY_TOO_SOON)
        self.last_retry = now

        self.client = Redis.from_url(self.dsn, **self.cfg)
        await self._redis_call(
            self.client.ping,
            mode="connect",
            operation="ping",
        )
        print(CacheMessages.REDIS_CONN_SUCCESS, flush=True)

    async def fetch(self, mode: str) -> TemperatureResult:
        """Fetches the latest cached temperature, validating its freshness."""
        if not self.client:
            await self.connect()

        raw = await self._redis_call(
            self.client.get,
            self.tag,
            mode=mode,
            operation="get",
        )

        try:
            cache = TemperatureResult.model_validate_json(raw)
        except ValidationError:
            raise CacheServiceError(CacheMessages.CACHE_INVALID)

        age = int(time.time()) - cache.timestamp

        if age < 3600:
            return cache

        raise CacheServiceError(CacheMessages.CACHE_OUTDATED)

    async def update(self, result: TemperatureResult, mode: str) -> None:
        """Stores a new TemperatureResult in the cache."""
        if not self.client:
            await self.connect()

        await self._redis_call(
            self.client.set,
            self.tag,
            result.model_dump_json(),
            mode=mode,
            operation="set",
        )