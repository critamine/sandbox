"""Test suite for CacheService module."""
# pylint: disable=unused-import,protected-access, redefined-outer-name
# ruff: noqa: F401, F811

from typing import Any, Callable, Generator, Literal
import pytest
from pytest_mock import MockerFixture

from hivebox.cache import (
    CacheMessages,
    CacheService,
    CacheServiceError
)
from tests.fixtures.cache_fixtures import (
    mock_redis_dsn,
    mock_redis_config
)

def test_cachesvc_init(mock_redis_dsn: Literal['redis://127.0.0.0:6379/0'], mock_redis_config: dict[str, Any]):
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
    service = CacheService(mock_redis_dsn, mock_redis_config)
    service.last_retry = 1000000
    mocker.patch("time.time", return_value=1000301)  # >5 min after last_retry

    mock_redis_client = mocker.Mock()
    mock_redis_client.ping = mocker.AsyncMock(return_value=True)
    mocker.patch("hivebox.cache.Redis.from_url", new=mocker.AsyncMock(return_value=mock_redis_client))

    await service.connect()
    out, _err = capfd.readouterr()
    assert CacheMessages.REDIS_CONN_SUCCESS in out
    assert service.client is mock_redis_client