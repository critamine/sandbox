# ruff: noqa
from datetime import datetime, timezone, timedelta
import pytest
from tests.fixtures.test_data import (
    sample_temperature_data,
    raw_temperature_data,
    mock_sensor_data,
    sample_trimmed_data
)
from hivebox.temperature import (
    avg_data,
    trim_data,
    validate_data,
    get_temperature_status,
    get_average_temperature,
    TemperatureServiceError,
    TemperatureReading
)

def test_avg_data_empty_dict(sample_temperature_data):
    with pytest.raises(ZeroDivisionError):
        avg_data({})
    assert avg_data(sample_temperature_data) == 21

def test_trim_data(raw_temperature_data, sample_trimmed_data):
    assert trim_data(raw_temperature_data) == sample_trimmed_data

def test_validate_data():
    now = datetime.now(timezone.utc)
    recent_time = (now - timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
    old_time = (now - timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%SZ')

    data = {
        'box1': {'name': 'Sensor 1', 'last': {'createdAt': recent_time}},
        'box2': {'name': 'Sensor 2', 'last': {'createdAt': old_time}}
    }
    validated = validate_data(data)
    assert 'box1' in validated
    assert 'box2' not in validated

@pytest.mark.parametrize("temp, expected_status", [
    (5, "Too Cold"),
    (25, "Good"),
    (40, "Too Hot"),
    (None, "No Data")
])
def test_temperature_status(temp, expected_status):
    assert get_temperature_status(temp) == expected_status

def test_get_average_temperature(mocker, mock_sensor_data):
    mocker.patch('hivebox.temperature.parse_data', return_value=mock_sensor_data)
    result = get_average_temperature()
    assert isinstance(result, TemperatureReading)
    assert result.value == 21
    assert result.status == "Good"

def test_get_average_temperature_error(mocker):
    mocker.patch('hivebox.temperature.parse_data', side_effect=TimeoutError("Connection timeout"))
    with pytest.raises(TemperatureServiceError) as exc:
        get_average_temperature()
    assert "Failed to fetch temperature data" in str(exc.value)


"""Temperature data processing module."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import requests
from . import SENSE_BOX_IDS, get_url

class TemperatureServiceError(Exception):
    pass

@dataclass
class TemperatureReading:
    value: float
    status: str

def parse_data():
    """Fetch raw temperature data from all sensor boxes."""
    try:
        return {
            sense_box_id: fetch_data(sense_box_id)
            for sense_box_id in SENSE_BOX_IDS
        }
    except requests.Timeout:
        raise 

def fetch_data(sense_box_id):
    """Helper function to fetch data from a single sensor box"""
    timeout = 10  
    try:
        response = requests.get(get_url(sense_box_id), timeout=timeout)
        if response.status_code == 200:
            return response.json()
        return f"Error: {response.status_code}"
    except requests.Timeout:
        raise

def trim_data(raw_data):
    """Extract relevant temperature data from raw sensor data."""
    return {
        box_id: {
            'name': data.get('name'),
            'last': next(
                (sensor['lastMeasurement']
                for sensor in data.get('sensors', [])
                if sensor.get('title') == 'Temperatur' and 'lastMeasurement' in sensor),
                None
            )
        }
        for box_id, data in raw_data.items()
        if isinstance(data, dict) and data.get('name')
    }

def validate_data(trimmed_data):
    """Filter data to include only recent measurements."""
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)

    return {
        box_id: data
        for box_id, data in trimmed_data.items()
        if data['last'] and is_recent_data(data['last']['createdAt'], one_hour_ago)
    }

def is_recent_data(timestamp: str, cutoff: datetime) -> bool:
    """Check if timestamp is more recent than cutoff."""
    normalized_timestamp = timestamp.replace('Z', '+00:00')
    parsed_time = datetime.fromisoformat(normalized_timestamp)
    return parsed_time > cutoff

def avg_data(trimmed_result):
    """Calculate average temperature from valid sensors, returns None if no data available."""
    temperatures = [
        float(box['last']['value'])
        for box in trimmed_result.values()
        if box['last'] and 'value' in box['last']
    ]

    try:
        return int(sum(temperatures) / len(temperatures))
    except ZeroDivisionError:
        raise

def get_temperature_status(averaged_result: int) -> str:
    """Returns a temperature status string based on input value"""
    if averaged_result is None:
        return "No Data"
    if averaged_result <= 10:
        return "Too Cold"
    if averaged_result <= 36:
        return "Good"
    return "Too Hot"

def get_average_temperature() -> TemperatureReading:
    """Get current average temperature from all valid sensors."""
    try:
        result = parse_data()
        trimmed_result = trim_data(result)
        print(trimmed_result)
        validated_result = validate_data(trimmed_result)
        averaged_result = avg_data(validated_result)
        temperature_status = get_temperature_status(averaged_result)
        return TemperatureReading(
            value=averaged_result,
            status=temperature_status
        )
    except (TimeoutError) as e:
        raise TemperatureServiceError(f"Failed to fetch temperature data: {str(e)}")
    except ValueError as e:
        raise TemperatureServiceError(f"Invalid temperature data: {str(e)}")
    except Exception as e:
        raise TemperatureServiceError(f"Error processing temperature data: {str(e)}")

"""Test suite for main API endpoints."""

import prometheus_client
from fastapi.testclient import TestClient
from hivebox.temperature import TemperatureServiceError, TemperatureReading
from main import app

client = TestClient(app)

def test_get_version():
    response = client.get("/version")
    assert response.status_code == 200
    assert "hivebox" in response.json()
    assert isinstance(response.json()["hivebox"], str)

def test_get_temperature(mocker):
    mock_reading = TemperatureReading(value=21.0, status="Good")
    mocker.patch('main.get_average_temperature', return_value=mock_reading)
    response = client.get("/temperature")
    assert response.status_code == 200
    assert response.json() == {"temperature": 21.0, "status": "Good"}

def test_get_temperature_error(mocker):
    mocker.patch('main.get_average_temperature', 
    side_effect=TemperatureServiceError("Service error"))
    response = client.get("/temperature")
    assert response.status_code == 503
    assert "Service error" in response.json()["detail"]

def test_metrics():
    test_counter = prometheus_client.Counter('test_counter', 'Test metric')
    test_counter.inc()
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert 'test_counter' in response.text
