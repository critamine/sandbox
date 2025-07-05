"""Tests CacheService & StorageService attachment during FastAPI lifespan."""
# pylint: disable=unused-import,protected-access,redefined-outer-name
# ruff: noqa: F401, F811

import types
from unittest.mock import Mock
import pytest
from fastapi import FastAPI

from hivebox.cache import CacheMessages, CacheServiceError
from hivebox.store import StorageServiceError

def _patch_scheduler(mocker):
    """Replace main.sched with a no-op stub."""
    stub = types.SimpleNamespace(
        start=Mock(),
        shutdown=Mock(),
        add_job=Mock(),
        reschedule_job=Mock(),
    )
    mocker.patch("main.sched", stub)

# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _fake_settings() -> types.SimpleNamespace:
    """Dummy Settings object with just the attrs lifespan() touches."""
    def dump(mode: str = "json") -> dict:
        return {}
    return types.SimpleNamespace(
        s3_config=types.SimpleNamespace(model_dump=dump),
        s3_endpoint_url="http://s3.local",
        s3_bucket="dummy",
        boto3_config=types.SimpleNamespace(model_dump=dump),
        redis_config=types.SimpleNamespace(model_dump=dump),
        redis_url="redis://localhost:6379",
        tmp_sensors=[],
        osm_base_url="http://osm.local",
    )

# --------------------------------------------------------------------------- #
# Tests – CacheService                                                        #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_lifespan_cacheservice_attach_success(mocker):
    """CacheService is attached on a successful connect()."""
    mocker.patch("main.get_settings", return_value=_fake_settings())

    MockStorageService = mocker.patch("main.StorageService", autospec=True)
    MockStorageService.return_value.connect = mocker.AsyncMock()

    MockCacheService = mocker.patch("main.CacheService", autospec=True)
    mock_cache = MockCacheService.return_value
    mock_cache.connect = mocker.AsyncMock()

    from main import lifespan

    app = FastAPI()
    async with lifespan(app):
        assert app.state.cache_svc is mock_cache
        mock_cache.connect.assert_awaited_once()

@pytest.mark.asyncio
async def test_lifespan_cacheservice_connect_failure(mocker, capsys):
    _patch_scheduler(mocker)
    """connect() failure is swallowed & message is printed."""
    mocker.patch("main.get_settings", return_value=_fake_settings())

    MockStorageService = mocker.patch("main.StorageService", autospec=True)
    MockStorageService.return_value.connect = mocker.AsyncMock()

    MockCacheService = mocker.patch("main.CacheService", autospec=True)
    mock_cache = MockCacheService.return_value
    mock_cache.connect = mocker.AsyncMock(
        side_effect=CacheServiceError(CacheMessages.REDIS_CONN_FAIL)
    )

    from main import lifespan

    app = FastAPI()
    async with lifespan(app):
        assert app.state.cache_svc is mock_cache

    out, _ = capsys.readouterr()
    assert CacheMessages.REDIS_CONN_FAIL in out

# --------------------------------------------------------------------------- #
# Tests – StorageService (bonus)                                              #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_lifespan_storageservice_connect_failure(mocker):
    """If the S3 connect explodes we propagate the error up."""
    mocker.patch("main.get_settings", return_value=_fake_settings())

    MockStorageService = mocker.patch("main.StorageService", autospec=True)
    MockStorageService.return_value.connect = mocker.AsyncMock(
        side_effect=StorageServiceError
    )
    MockCacheService = mocker.patch("main.CacheService", autospec=True)
    MockCacheService.return_value.connect = mocker.AsyncMock()

    from main import lifespan
    app = FastAPI()
    with pytest.raises(StorageServiceError):
        async with lifespan(app):
            pass