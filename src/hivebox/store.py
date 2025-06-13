"""S3-compatible object-storage module (async)."""

import datetime as dt
import aioboto3
from pydantic import HttpUrl
from botocore.exceptions import EndpointConnectionError
from botocore.config import Config
from hivebox.temperature import TemperatureResult


class StorageMessages:
    """Static message strings."""

    S3_CONN_FAIL = "Connection to S3 server failed"
    S3_CONN_SUCCESS = "Connection to S3 server succeeded"
    S3_UPLOAD_FAIL = "latest.json upload to S3 server failed"
    S3_FETCH_FAIL = "Fetch from S3 server failed"
    RETRY_TOO_SOON = "S3 reconnect attempted too soon"


class StorageServiceError(Exception):
    """Raised when storage-service operations fail."""


class StorageService:
    """Handles temperature-data storage and retrieval via S3."""

    def __init__(
        self,
        s3_endpoint_url: HttpUrl,
        s3_config: dict,
        b3_config: dict,
        s3_bucket: str
    ):
        self.url = str(s3_endpoint_url)
        self.s3_cfg = s3_config
        self.b3_cfg = Config(**b3_config)
        self.last_retry = None
        self.session = aioboto3.Session()
        self._cm = None
        self.client = None
        self.bucket = s3_bucket
        self.latest_key = "latest.json"

    async def connect(self):
        """Lazy-open an async S3 client, respecting 5-min back-off."""
        now = int(dt.datetime.now().timestamp())
        if self.last_retry and (now - self.last_retry) < 300:
            raise StorageServiceError(StorageMessages.RETRY_TOO_SOON)
        self.last_retry = now

        self._cm = self.session.client(
            "s3",
            endpoint_url=self.url,
            config=self.b3_cfg,
            **self.s3_cfg,
        )
        try:
            self.client = await self._cm.__aenter__()
            await self._verify_bucket_access()
            print(StorageMessages.S3_CONN_SUCCESS, flush=True)
        except Exception as e:
            if self._cm:
                await self._cm.__aexit__(type(e), e, None)
                self._cm = None
            self.client = None
            raise StorageServiceError(StorageMessages.S3_CONN_FAIL) from e

    async def _verify_bucket_access(self):
        try:
            await self.client.head_bucket(Bucket=self.bucket)

            test_key = "__health_check.txt"
            payload  = b"ping"

            put_resp = await self.client.put_object(
                Bucket=self.bucket,
                Key=test_key,
                Body=payload
            )
            assert put_resp["ResponseMetadata"]["HTTPStatusCode"] == 200

            get_resp = await self.client.get_object(
                Bucket=self.bucket,
                Key=test_key
            )
            assert await get_resp["Body"].read() == payload

            del_resp = await self.client.delete_object(
                Bucket=self.bucket,
                Key=test_key
            )
            assert del_resp["ResponseMetadata"]["HTTPStatusCode"] in (200, 204)

        except Exception:
            print("Failed verify", flush=True)
            raise

    async def store_temperature_result(self, temp: TemperatureResult):
        json_payload = temp.model_dump_json().encode()
        try:
            await self.client.put_object(
                Bucket=self.bucket,
                Key=self.latest_key,
                Body=json_payload,
                ContentType="application/json",
            )
        except Exception as e:
            raise StorageServiceError(f"{StorageMessages.S3_UPLOAD_FAIL}: {e}")
    
    async def get_stored_temperature(self):
        try:
            resp = await self.client.get_object(
                Bucket=self.bucket,
                Key=self.latest_key
            )
        except EndpointConnectionError:
            await self.connect()
            resp = await self.client.get_object(
                Bucket=self.bucket,
                Key=self.latest_key
            )
        try:
            raw: bytes = await resp["Body"].read()
            model = TemperatureResult.model_validate_json(raw)
            ts = resp["LastModified"]
            age = int((dt.datetime.now(ts.tzinfo) - ts).total_seconds())
            if age < 3600:
                return model, age
        except Exception:
            raise StorageServiceError(StorageMessages.S3_FETCH_FAIL)