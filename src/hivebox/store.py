"""S3-compatible object-storage module (refactored)."""

import datetime as dt
import time
import aioboto3
import asyncio
from socket import gaierror
from pydantic import HttpUrl
from hivebox.metrics import (
    S3_CALLS,
    S3_LATENCY,
    DEPENDENCY_RECONNECT_THROTTLED,
)
from botocore.exceptions import EndpointConnectionError, ClientError
from botocore.config import Config
from hivebox.temperature import TemperatureResult

class StorageMessages:
    """Static message strings."""
    S3_CONN_FAIL     = "Connection to S3 server failed"
    S3_CONN_SUCCESS  = "Connection to S3 server succeeded"
    S3_UPLOAD_FAIL   = "Upload to S3 server failed"
    S3_FETCH_FAIL    = "Fetch from S3 server failed"
    RETRY_TOO_SOON   = "S3 reconnect attempted too soon"

class StorageServiceError(Exception):
    """Raised when storage-service operations fail."""

class StorageService:
    """Handles temperature-data storage and retrieval via S3."""

    def __init__(
        self,
        s3_endpoint_url: HttpUrl,
        s3_config: dict,
        b3_config: dict,
        s3_bucket: str,
    ):
        self.url        = str(s3_endpoint_url)
        self.s3_cfg     = s3_config
        self.b3_cfg     = Config(**b3_config)
        self.bucket     = s3_bucket
        self.latest_key = "latest.json"

        self.session     = aioboto3.Session()
        self._cm         = None
        self.client      = None
        self.last_retry  = None

    # ───────────────────────────────── S3 CALL WRAPPER ─────────────────────────

    async def _s3_call(
        self,
        s3_method,
        *args,
        mode: str,
        operation: str,
        **kwargs,
    ):
        """
        Centralised S3 call wrapper:
          • automatic 1x reconnect retry (same logic as _redis_call)
          • metrics & latency
        """
        start   = time.time()
        result  = "error"
        try:
            for attempt in (1, 2):
                try:
                    resp   = await s3_method(*args, **kwargs)
                    result = "success"
                    return resp
                except (EndpointConnectionError, ClientError, AttributeError, asyncio.CancelledError, gaierror) as e:
                    if attempt == 1 and mode != "connect":
                        await self.connect()
                        continue
                    raise StorageServiceError(StorageMessages.S3_CONN_FAIL) from e
        finally:
            lat = time.time() - start
            S3_CALLS.labels(mode=mode, operation=operation, result=result).inc()
            S3_LATENCY.labels(operation=operation, result=result).observe(lat)

    # ───────────────────────────────── CONNECTION ──────────────────────────────

    async def connect(self):
        """(Re)open an async S3 client, respecting 5-min back-off."""
        now = int(time.time())
        if self.last_retry and (now - self.last_retry) < 300:
            DEPENDENCY_RECONNECT_THROTTLED.labels(dependency="s3").inc()
            raise StorageServiceError(StorageMessages.RETRY_TOO_SOON)
        self.last_retry = now

        # close any previous CM cleanly
        if self._cm:
            await self._cm.__aexit__(None, None, None)
            self._cm = None
            self.client = None

        self._cm = self.session.client(
            "s3",
            endpoint_url=self.url,
            config=self.b3_cfg,
            **self.s3_cfg,
        )

        # Will raise if creds/endpoint are bad; counts as a connect op
        self.client = await self._cm.__aenter__()
        await self._verify_bucket_access()
        print(StorageMessages.S3_CONN_SUCCESS, flush=True)

    # ─────────────────────────────── BUCKET HEALTH ─────────────────────────────

    async def _verify_bucket_access(self):
        """Lightweight R/W sanity test on the configured bucket."""
        test_key = "__health_check.txt"
        payload  = b"ping"

        await self._s3_call(
            self.client.head_bucket,
            mode="connect",
            operation="head",
            Bucket=self.bucket,
        )
        put_resp = await self._s3_call(
            self.client.put_object,
            mode="connect",
            operation="put",
            Bucket=self.bucket,
            Key=test_key,
            Body=payload,
        )
        assert put_resp["ResponseMetadata"]["HTTPStatusCode"] == 200

        get_resp = await self._s3_call(
            self.client.get_object,
            mode="connect",
            operation="get",
            Bucket=self.bucket,
            Key=test_key,
        )
        assert await get_resp["Body"].read() == payload

        del_resp = await self._s3_call(
            self.client.delete_object,
            mode="connect",
            operation="delete",
            Bucket=self.bucket,
            Key=test_key,
        )
        assert del_resp["ResponseMetadata"]["HTTPStatusCode"] in (200, 204)

    # ─────────────────────────── PUBLIC INTERFACE ──────────────────────────────

    async def store_temperature_result(self, temp: TemperatureResult, mode: str):
        """"Upload a TemperatureResult JSON blob to S3."""  # ← docstring
        if not self.client:
            await self.connect()

        try:
            await self._s3_call(
                self.client.put_object,
                mode=mode,
                operation="put",
                Bucket=self.bucket,
                Key=self.latest_key,
                Body=temp.model_dump_json().encode(),
                ContentType="application/json",
            )
        except Exception as e:
            raise StorageServiceError(f"{StorageMessages.S3_UPLOAD_FAIL}: {e}")

    async def get_stored_temperature(self, mode: str):
        """"Fetch latest TemperatureResult + its age (seconds)."""
        if not self.client:
            await self.connect()

        resp = await self._s3_call(
            self.client.get_object,
            mode=mode,
            operation="get",
            Bucket=self.bucket,
            Key=self.latest_key,
        )

        try:
            raw   = await resp["Body"].read()
            model = TemperatureResult.model_validate_json(raw)

            ts   = resp["LastModified"]
            age  = int((dt.datetime.now(ts.tzinfo) - ts).total_seconds())
            if age < 3600:
                return model, age
        except Exception:
            pass  # fall through to error below

        raise StorageServiceError(StorageMessages.S3_FETCH_FAIL)