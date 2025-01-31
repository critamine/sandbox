"""Test fixtures for temperature service module."""

from datetime import datetime, timezone, timedelta
import pytest

@pytest.fixture
def mock_sensor_data():
    """Return mock mapping of box IDs to sensor IDs."""
    return {
        'senseBox01': 'tempSensor01',
        'senseBox02': 'tempSensor02',
        'senseBox03': 'tempSensor03'
    }

@pytest.fixture
def mock_temperature_averages():
    """Return test cases for temperature status determinations."""
    return [
        (5.0, "Too Cold"),
        (10.0, "Too Cold"),
        (11.0, "Good"),
        (25.0, "Good"),
        (36.0, "Good"),
        (37.0, "Too Hot"),
        (40.0, "Too Hot"),
    ]

@pytest.fixture
def mock_sensor_responses():
    """Return mock sensor responses with current timestamps."""
    current_time = datetime.now(timezone.utc).isoformat()
    return {
        "tempSensor01": {
            "lastMeasurement": {
                "createdAt": current_time,
                "value": "15.5"
            }
        },
        "tempSensor02": {
            "lastMeasurement": {
                "createdAt": current_time,
                "value": "17.3"
            }
        },
        "tempSensor03": {
            "lastMeasurement": {
                "createdAt": current_time,
                "value": "16.2"
            }
        }
    }

@pytest.fixture
def mock_sensor_responses_stale():
    """Return mock sensor responses with timestamps older than one hour."""
    two_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    return {
        "tempSensor01": {
            "lastMeasurement": {
                "createdAt": two_hours_ago,
                "value": "15.5"
            }
        },
        "tempSensor02": {
            "lastMeasurement": {
                "createdAt": two_hours_ago,
                "value": "17.3"
            }
        },
        "tempSensor03": {
            "lastMeasurement": {
                "createdAt": two_hours_ago,
                "value": "16.2"
            }
        }
    }

@pytest.fixture
def mock_sensor_responses_invalid_json():
    """Return mock sensor responses with invalid JSON syntax."""
    return {
        "tempSensor01": "{invalid[json'syntax",
        "tempSensor02": "{'lastMeasurement': {",
        "tempSensor03": "null{]"
    }

@pytest.fixture
def mock_sensor_responses_invalid_value():
    """Return mock sensor response with non-numeric temperature value."""
    current_time = datetime.now(timezone.utc).isoformat()
    return {
        "tempSensor01": {
            "lastMeasurement": {
                "createdAt": current_time,
                "value": "not a number"
            }
        }
    }
