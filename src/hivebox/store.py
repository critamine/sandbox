"""S3-compatible object-storage module."""

import time
import boto3
from pydantic import HttpUrl

class StorageMessages:
    """Static message strings."""
    S3_CONN_FAIL     = "Connection to S3 server failed"
    S3_CONN_SUCCESS  = "Connection to S3 server succeeded"
    RETRY_TOO_SOON   = "S3 reconnect attempted too soon"

class StorageServiceError(Exception):
    """Raised when storage-service operations fail."""
    pass

class StorageService:
    """Handles temperature-data storage and retrieval via S3."""

    def __init__(self, s3_endpoint_url: HttpUrl, s3_cfg: dict):
        self.url          = str(s3_endpoint_url)
        print(self.url)
        self.cfg          = s3_cfg
        self.last_retry   = None

        self.client = boto3.client(
            "s3",
            endpoint_url=self.url,
            **self.cfg
        )

    async def connect(self):
        now = int(time.time())

        if self.last_retry is not None and (now - self.last_retry) < 300:
            raise StorageServiceError(StorageMessages.RETRY_TOO_SOON)

        self.last_retry = now

        try:
            print(self.client.list_buckets())
            print(StorageMessages.S3_CONN_SUCCESS, flush=True)
        except Exception:
            print(StorageMessages.S3_CONN_FAIL, flush=True)