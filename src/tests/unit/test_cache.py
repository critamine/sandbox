"""Test suite for CacheService module."""
# pylint: disable=unused-import,protected-access, redefined-outer-name
# ruff: noqa: F401, F811

import time
from typing import Any, Callable, Generator, Literal
import pytest
from pytest_mock import MockerFixture
from pytest_mock.plugin import _mocker

from hivebox.cache import (
    CacheMessages,
    CacheService,
    CacheServiceError
)
from hivebox.temperature import (
    TemperatureResult
)
from tests.fixtures.cache_fixtures import (
    mock_deserialized_cache_data,
    mock_serialized_cache_data,
    mock_redis_dsn,
    mock_redis_config
)

def test_cachesvc_init(
        mock_redis_dsn: Literal['redis://127.0.0.0:6379/0'], 
        mock_redis_config: dict[str, Any]
):
    """Test that CacheService initializes with the correct DSN and config."""
    service = CacheService(mock_redis_dsn, mock_redis_config)
    assert service.dsn == mock_redis_dsn
    assert service.cfg == mock_redis_config

@pytest.mark.asyncio
async def test_cachesvc_connectfail(
    mock_redis_dsn: Literal['redis://127.0.0.0:6379/0'],
    mock_redis_config: dict[str, Any],
    mocker: Callable[..., Generator[MockerFixture, None, None]],
    capfd: pytest.CaptureFixture[str]
):
    """Test connect() prints failure message on error."""
    service = CacheService(mock_redis_dsn, mock_redis_config)
    service.last_retry = 1000212360
    mocker.patch("time.time", return_value=1000213380)

    await service.connect()
    out, _err = capfd.readouterr()
    assert CacheMessages.REDIS_CONN_FAIL in out

@pytest.mark.asyncio
async def test_cachesvc_connect_toosoon(
    mock_redis_dsn: Literal['redis://127.0.0.0:6379/0'],
    mock_redis_config: dict[str, Any],
    mocker: Callable[..., Generator[MockerFixture, None, None]]
):
    """Test connect() raises error if called too soon."""
    service = CacheService(mock_redis_dsn, mock_redis_config)
    service.last_retry = 1000000
    mocker.patch("time.time", return_value=1000000)

    with pytest.raises(CacheServiceError) as exc:
        await service.connect()
    assert CacheMessages.RETRY_TOO_SOON in str(exc.value)

@pytest.mark.asyncio
async def test_cachesvc_connect_success(
    mock_redis_dsn: Literal['redis://127.0.0.0:6379/0'],
    mock_redis_config: dict[str, Any],
    mocker: Callable[..., Generator[MockerFixture, None, None]],
    capfd: pytest.CaptureFixture[str]
):
    """Test connect() succeeds after retry interval."""
    mock_redis_client = mocker.Mock()
    mock_redis_client.ping = mocker.AsyncMock(return_value=True)
    mocker.patch("hivebox.cache.Redis.from_url", return_value=mock_redis_client)

    service = CacheService(mock_redis_dsn, mock_redis_config)
    service.last_retry = 1000000
    mocker.patch("time.time", return_value=1000301)

    await service.connect()
    out, _err = capfd.readouterr()
    assert CacheMessages.REDIS_CONN_SUCCESS in out
    assert service.client is mock_redis_client

@pytest.mark.asyncio
async def test_cachesvc_check_fail(
    mock_redis_dsn: Literal['redis://127.0.0.0:6379/0'],
    mock_redis_config: dict[str, Any],
    mock_deserialized_cache_data: TemperatureResult,
):
    """Test _check() returns False for old cache timestamp."""
    service = CacheService(mock_redis_dsn, mock_redis_config)
    cache = mock_deserialized_cache_data
    cache.timestamp = 1000
    assert not await service._check(cache)

@pytest.mark.asyncio
async def test_cachesvc_check_pass(
    mock_redis_dsn: Literal['redis://127.0.0.0:6379/0'],
    mock_redis_config: dict[str, Any],
    mock_deserialized_cache_data: TemperatureResult,
):
    """Test _check() returns True for recent cache timestamp."""
    service = CacheService(mock_redis_dsn, mock_redis_config)
    cache = mock_deserialized_cache_data
    cache.timestamp = int(time.time())
    assert await service._check(cache) is True

@pytest.mark.asyncio
async def test_cachesvc_fetch_success(
    mock_redis_dsn: Literal['redis://127.0.0.0:6379/0'],
    mock_redis_config: dict[str, Any],
    mock_serialized_cache_data,
    mocker: Callable[..., Generator[MockerFixture, None, None]],
):
    """Test fetch() returns valid TemperatureResult"""
    mock_redis_client = mocker.Mock()
    mock_redis_client.get = mocker.AsyncMock(return_value=mock_serialized_cache_data)
    mocker.patch("hivebox.cache.Redis.from_url", return_value=mock_redis_client)
    service = CacheService(mock_redis_dsn, mock_redis_config)
    mocker.patch.object(service, '_check', return_value=True)

    cache = await service.fetch()
    assert isinstance(cache, TemperatureResult)

@pytest.mark.asyncio
async def test_cachesvc_fetch_no_data(
    mock_redis_dsn: Literal['redis://127.0.0.0:6379/0'],
    mock_redis_config: dict[str, Any],
    mocker: Callable[..., Generator[MockerFixture, None, None]],
):
    """Test fetch() when no data exists in Redis (returns None)."""
    mock_redis_client = mocker.Mock()
    mock_redis_client.get = mocker.AsyncMock(return_value=None)
    mocker.patch("hivebox.cache.Redis.from_url", return_value=mock_redis_client)
    service = CacheService(mock_redis_dsn, mock_redis_config)

    with pytest.raises(CacheServiceError, match=CacheMessages.CACHE_INVALID):
        await service.fetch()

@pytest.mark.asyncio
async def test_cachesvc_fetch_malformed_json(
    mock_redis_dsn: Literal['redis://127.0.0.0:6379/0'],
    mock_redis_config: dict[str, Any],
    mocker: Callable[..., Generator[MockerFixture, None, None]],
):
    """Test fetch() with malformed JSON data."""
    mock_redis_client = mocker.Mock()
    mock_redis_client.get = mocker.AsyncMock(return_value='{"invalid": json}')
    mocker.patch("hivebox.cache.Redis.from_url", return_value=mock_redis_client)
    service = CacheService(mock_redis_dsn, mock_redis_config)

    with pytest.raises(CacheServiceError, match=CacheMessages.CACHE_INVALID):
        await service.fetch()

@pytest.mark.asyncio
async def test_cachesvc_fetch_outdated_cache(
    mock_redis_dsn: Literal['redis://127.0.0.0:6379/0'],
    mock_redis_config: dict[str, Any],
    mock_serialized_cache_data,
    mocker: Callable[..., Generator[MockerFixture, None, None]],
):
    """Test fetch() when cache is outdated."""
    mock_redis_client = mocker.Mock()
    mock_redis_client.get = mocker.AsyncMock(return_value=mock_serialized_cache_data)
    mocker.patch("hivebox.cache.Redis.from_url", return_value=mock_redis_client)
    service = CacheService(mock_redis_dsn, mock_redis_config)
    mocker.patch.object(service, '_check', return_value=False)

    with pytest.raises(CacheServiceError, match=CacheMessages.CACHE_OUTDATED):
            await service.fetch()