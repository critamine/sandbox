"""Tests Redis CacheService initialization and attachment to FastAPI app state during lifespan."""
# pylint: disable=unused-import,protected-access, redefined-outer-name
# ruff: noqa: F401, F811

import pytest
from fastapi import FastAPI
from pytest_mock import MockerFixture
from main import lifespan
from hivebox.cache import CacheService, CacheMessages, CacheServiceError

@pytest.mark.asyncio
async def test_lifespan_cacheservice_attach_success(mocker):
    """Checks CacheService attaches to app.state on connect success."""
    MockCacheService = mocker.patch("main.CacheService", autospec=True)
    mock_cache = MockCacheService.return_value
    mock_cache.connect = mocker.AsyncMock(return_value=None)

    app = FastAPI()
    async with lifespan(app):
        assert hasattr(app.state, "cache_svc")
        assert app.state.cache_svc is mock_cache
        mock_cache.connect.assert_awaited_once()

@pytest.mark.asyncio
async def test_lifespan_cacheservice_connect_failure(mocker, capsys):
    MockCacheService = mocker.patch("main.CacheService", autospec=True)
    mock_cache = MockCacheService.return_value
    mock_cache.connect = mocker.AsyncMock(side_effect=CacheServiceError)

    app = FastAPI()
    async with lifespan(app):
        assert hasattr(app.state, "cache_svc")
        assert app.state.cache_svc is mock_cache

    captured = capsys.readouterr()
    assert CacheMessages.REDIS_CONN_FAIL in captured.out