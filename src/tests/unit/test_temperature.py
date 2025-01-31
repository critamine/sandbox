"""Test suite for temperature data processing module."""
# pylint: disable=unused-import,protected-access, redefined-outer-name
# ruff: noqa: F401, F811

import json
import pytest
import requests

from tests.fixtures.temperature_fixtures import (
    mock_temperature_averages,
    mock_sensor_data,
    mock_sensor_responses,
    mock_sensor_responses_stale,
    mock_sensor_responses_invalid_json,
    mock_sensor_responses_invalid_value
)
from hivebox.temperature import (
    TemperatureService,
    TemperatureServiceError
)


def test_temperatureservice_init(mock_sensor_data):
    """Test successful initialization of TemperatureService with sensor data."""
    service = TemperatureService(mock_sensor_data)
    assert service.sensor_data == mock_sensor_data


def test_temperatureservice_init_nodata():
    """Test TemperatureService initialization with empty sensor data."""
    with pytest.raises(TemperatureServiceError) as e:
        TemperatureService({})
    assert str(e.value == "No sensor data provided")


@pytest.mark.parametrize("temperature,expected_status", [
    (5.0, "Too Cold"),
    (10.0, "Too Cold"),
    (11.0, "Good"),
    (25.0, "Good"),
    (36.0, "Good"),
    (37.0, "Too Hot"),
    (40.0, "Too Hot"),
])
def test_determine_temperature_status(mock_sensor_data, temperature, expected_status):
    """Test determination of temperature status for various input values."""
    service = TemperatureService(mock_sensor_data)
    status = service._determine_temperature_status(temperature)
    assert status == expected_status


def test_get_average_temperature(mock_sensor_data, mock_sensor_responses, mocker):
    """Test calculating average temperature from multiple sensor readings."""
    mock_get = mocker.patch('requests.get')

    mock_get.return_value.json.side_effect = [
        mock_sensor_responses["tempSensor01"],
        mock_sensor_responses["tempSensor02"],
        mock_sensor_responses["tempSensor03"]
    ]
    mock_get.return_value.raise_for_status.return_value = None

    service = TemperatureService(mock_sensor_data)
    result = service.get_average_temperature()

    assert result.value == 16.3
    assert result.status == "Good"
    assert mock_get.call_count == 3


def test_fetch_readings_successful(mock_sensor_data, mock_sensor_responses, mocker):
    """Test successful fetch of sensor readings."""
    mock_get = mocker.patch('requests.get')
    mock_get.return_value.json.side_effect = [
        mock_sensor_responses["tempSensor01"],
        mock_sensor_responses["tempSensor02"],
        mock_sensor_responses["tempSensor03"]
    ]
    mock_get.return_value.raise_for_status.return_value = None

    service = TemperatureService(mock_sensor_data)
    readings = service._fetch_readings()

    assert len(readings) == 3

    for reading in readings:
        assert hasattr(reading, 'sensor_id')
        assert hasattr(reading, 'value')
        assert hasattr(reading, 'timestamp')
        assert isinstance(reading.value, float)
        assert reading.sensor_id in ["tempSensor01", "tempSensor02", "tempSensor03"]

    assert mock_get.call_count == 3


def test_fetch_readings_stale(mock_sensor_data, mock_sensor_responses_stale, mocker):
    """Test behavior when all sensor readings are older than one hour."""
    mock_get = mocker.patch('requests.get')
    mock_get.return_value.json.side_effect = [
        mock_sensor_responses_stale["tempSensor01"],
        mock_sensor_responses_stale["tempSensor02"],
        mock_sensor_responses_stale["tempSensor03"]
    ]
    mock_get.return_value.raise_for_status.return_value = None

    service = TemperatureService(mock_sensor_data)

    with pytest.raises(TemperatureServiceError) as e:
        service._fetch_readings()
    assert str(e.value) == "All available readings are over 1 hour old"


def test_fetch_readings_connection_error(mock_sensor_data, mocker):
    """Test handling of connection errors during sensor reading fetch."""
    mock_get = mocker.patch('requests.get')
    mock_get.side_effect = requests.exceptions.ConnectionError()
    service = TemperatureService(mock_sensor_data)
    sensor_id = list(mock_sensor_data.values())[0]

    with pytest.raises(TemperatureServiceError) as e:
        service._fetch_readings()

    error_msg = str(e.value)
    assert f"Failed to fetch data for sensor {sensor_id}" in error_msg
    assert isinstance(mock_get.side_effect, requests.exceptions.ConnectionError)


def test_fetch_readings_invalid_json(mock_sensor_data, mock_sensor_responses_invalid_json, mocker):
    """Test handling of invalid JSON responses from sensors."""
    mock_get = mocker.patch('requests.get')
    mock_response = mocker.Mock()
    mock_response.json.side_effect = [
        json.JSONDecodeError('Invalid JSON',
        mock_sensor_responses_invalid_json["tempSensor01"], 0)
    ]
    mock_get.return_value = mock_response

    service = TemperatureService(mock_sensor_data)
    with pytest.raises(TemperatureServiceError) as e:
        service._fetch_readings()
    assert "Invalid data received from sensor" in str(e.value)


def test_fetch_readings_value_error(mock_sensor_data, mock_sensor_responses_invalid_value, mocker):
    """Test handling of invalid temperature value responses."""
    mock_get = mocker.patch('requests.get')
    mock_response = mocker.Mock()
    mock_response.json.return_value = mock_sensor_responses_invalid_value["tempSensor01"]
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    service = TemperatureService(mock_sensor_data)

    with pytest.raises(TemperatureServiceError) as e:
        service._fetch_readings()
    assert "Invalid data received from sensor" in str(e.value)
