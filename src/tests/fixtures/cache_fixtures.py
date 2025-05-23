"""Test fixtures for CacheService module."""

import pytest
from hivebox.temperature import (
    TemperatureResult
)

@pytest.fixture
def mock_redis_dsn():
    """Return mock Redis URL/DSN"""
    return "redis://127.0.0.0:6379/0"

@pytest.fixture
def mock_redis_config():
    """Return mock Redis config"""
    return {
        'encoding': 'utf-8',
        'decode_responses': True
    }

@pytest.fixture
def mock_serialized_cache_data():
    """Return mock cache JSON string"""
    return '{"value":14.8,"status":"Good","timestamp":1747774970}'

@pytest.fixture
def mock_deserialized_cache_data():
    """Return TemperatureResult object with mock data"""
    return TemperatureResult(
        value=14.8,
        status="Good",
        timestamp=1747774970
    )