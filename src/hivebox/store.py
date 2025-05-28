"""S3-compatible object-storage module (async)."""

import time
import aioboto3
from pydantic import HttpUrl

class StorageMessages:
    """Static message strings."""
    S3_CONN_FAIL   = "Connection to S3 server failed"
    S3_CONN_SUCCESS = "Connection to S3 server succeeded"
    RETRY_TOO_SOON = "S3 reconnect attempted too soon"

class StorageServiceError(Exception):
    """Raised when storage-service operations fail."""

class StorageService:
    """Handles temperature-data storage and retrieval via S3."""

    def __init__(self, s3_endpoint_url: HttpUrl, s3_cfg: dict):
        self.url         = str(s3_endpoint_url)
        self.cfg         = s3_cfg
        self.last_retry  = None
        self.session     = aioboto3.Session()
        self._cm         = None
        self.client      = None

    async def connect(self):
        """Lazy-open an async S3 client, respecting 5-min back-off."""
        now = int(time.time())
        if self.last_retry and (now - self.last_retry) < 300:
            raise StorageServiceError(StorageMessages.RETRY_TOO_SOON)
        self.last_retry = now

        self._cm = self.session.client("s3", endpoint_url=self.url, **self.cfg)
        try:
            self.client = await self._cm.__aenter__()
            await self.client.list_buckets()
            print(StorageMessages.S3_CONN_SUCCESS, flush=True)
        except Exception as exc:
            print(StorageMessages.S3_CONN_FAIL, flush=True)
            if self._cm:
                await self._cm.__aexit__(type(exc), exc, None)
                self._cm = None
            self.client = None
            raise