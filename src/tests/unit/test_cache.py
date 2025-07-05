"""Test suite for CacheService module."""
# pylint: disable=unused-import,protected-access, redefined-outer-name
# ruff: noqa: F401, F811

from typing import Any, Literal
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
    mocker: MockerFixture,
    capfd: pytest.CaptureFixture[str]
):
    """Test connect() prints failure message on error."""
    service = CacheService(mock_redis_dsn, mock_redis_config)
    service.last_retry = 1000212360
    mocker.patch("time.time", return_value=1000213380)

    with pytest.raises(CacheServiceError) as exc:
        await service.connect()
    assert CacheMessages.REDIS_CONN_FAIL in str(exc.value)

@pytest.mark.asyncio
async def test_cachesvc_connect_toosoon(
    mock_redis_dsn: Literal['redis://127.0.0.0:6379/0'],
    mock_redis_config: dict[str, Any],
    mocker: MockerFixture
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
    mocker: MockerFixture,
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
async def test_cachesvc_fetch_success(
    mock_redis_dsn: Literal['redis://127.0.0.0:6379/0'],
    mock_redis_config: dict[str, Any],
    mocker: MockerFixture,
):
    """Test fetch() returns a valid and fresh TemperatureResult."""
    current_time = 1700003600
    fresh_data = TemperatureResult(value=21.5, status="Good", timestamp=current_time - 1)

    mock_redis_client = mocker.Mock()
    mock_redis_client.get = mocker.AsyncMock(return_value=fresh_data.model_dump_json())
    mock_redis_client.ping = mocker.AsyncMock(return_value=True)
    mocker.patch("hivebox.cache.Redis.from_url", return_value=mock_redis_client)
    mocker.patch("time.time", return_value=current_time)
    service = CacheService(mock_redis_dsn, mock_redis_config)

    cache = await service.fetch("test")
    assert isinstance(cache, TemperatureResult)
    assert cache == fresh_data

@pytest.mark.asyncio
async def test_cachesvc_fetch_no_data(
    mock_redis_dsn: Literal['redis://127.0.0.0:6379/0'],
    mock_redis_config: dict[str, Any],
    mocker: MockerFixture,
):
    """Test fetch() when no data exists in Redis (returns None)."""
    mock_redis_client = mocker.Mock()
    mock_redis_client.get = mocker.AsyncMock(return_value=None)
    mock_redis_client.ping = mocker.AsyncMock(return_value=True)
    mocker.patch("hivebox.cache.Redis.from_url", return_value=mock_redis_client)
    service = CacheService(mock_redis_dsn, mock_redis_config)

    with pytest.raises(CacheServiceError, match=CacheMessages.CACHE_INVALID):
        await service.fetch("test")

@pytest.mark.asyncio
async def test_cachesvc_fetch_malformed_json(
    mock_redis_dsn: Literal['redis://127.0.0.0:6379/0'],
    mock_redis_config: dict[str, Any],
    mocker: MockerFixture,
):
    """Test fetch() with malformed JSON data."""
    mock_redis_client = mocker.Mock()
    mock_redis_client.get = mocker.AsyncMock(return_value='{"invalid": json}')
    mock_redis_client.ping = mocker.AsyncMock(return_value=True)
    mocker.patch("hivebox.cache.Redis.from_url", return_value=mock_redis_client)
    service = CacheService(mock_redis_dsn, mock_redis_config)

    with pytest.raises(CacheServiceError, match=CacheMessages.CACHE_INVALID):
        await service.fetch("test")

@pytest.mark.asyncio
async def test_cachesvc_fetch_outdated_cache(
    mock_redis_dsn: Literal['redis://127.0.0.0:6379/0'],
    mock_redis_config: dict[str, Any],
    mocker: MockerFixture,
):
    """Test fetch() raises an error when the cache is outdated."""
    current_time = 1700003601
    # Cache is 3601 seconds old, which is outdated
    stale_data = TemperatureResult(value=21.5, status="Good", timestamp=current_time - 3601)

    mock_redis_client = mocker.Mock()
    mock_redis_client.get = mocker.AsyncMock(return_value=stale_data.model_dump_json())
    mock_redis_client.ping = mocker.AsyncMock(return_value=True)
    mocker.patch("hivebox.cache.Redis.from_url", return_value=mock_redis_client)
    mocker.patch("time.time", return_value=current_time)
    service = CacheService(mock_redis_dsn, mock_redis_config)

    with pytest.raises(CacheServiceError, match=CacheMessages.CACHE_OUTDATED):
        await service.fetch("test")