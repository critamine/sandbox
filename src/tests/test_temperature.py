"""Test suite for temperature data processing functions."""

from datetime import datetime, timezone, timedelta
from hivebox.temperature import (
    is_recent_data,
    avg_data,
)

def test_avg_data():
    """Test average temperature calculation with empty and valid data."""
    assert avg_data({}) is None

    sample_data = {
        'sensor1': {'last': {'value': '20.5'}},
        'sensor2': {'last': {'value': '21.5'}}
    }
    assert avg_data(sample_data) == 21

def test_is_recent_data():
    """Test timestamp validation against cutoff time."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=1)

    recent = (now - timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
    old = (now - timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%SZ')

    assert is_recent_data(recent, cutoff)
    assert not is_recent_data(old, cutoff)
