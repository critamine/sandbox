"""Test fixtures for CacheService module."""

import pytest

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