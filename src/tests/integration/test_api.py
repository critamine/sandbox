"""Integration tests for the FastAPI application endpoints."""
# pylint: disable=unused-import,protected-access,redefined-outer-name,duplicate-code
# ruff: noqa: F401, F811

import pytest
import requests
from fastapi.testclient import TestClient
from hivebox import __version__
from hivebox.cache import CacheServiceError
from main import app
from tests.fixtures.temperature_fixtures import (
    mock_sensor_responses,
    mock_sensor_responses_stale,
    mock_sensor_responses_invalid_value
)

class DummyCacheService:
    async def fetch(self, *args, **kwargs):
        raise CacheServiceError("Cache unavailable")
    async def update(self, *args, **kwargs):
        raise CacheServiceError("Cache unavailable")
    
app.state.cache_svc = DummyCacheService()
client = TestClient(app)

def test_get_version():
    """Test that version endpoint returns correct version information."""
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json() == {"hivebox": __version__}

def test_get_temperature_success(mocker, mock_sensor_responses):
    """Test successful temperature readings from all sensors."""
    mock_get = mocker.patch('requests.get')
    mock_get.return_value.json.side_effect = [
        mock_sensor_responses["tempSensor01"],
        mock_sensor_responses["tempSensor02"],
        mock_sensor_responses["tempSensor03"]
    ]

    response = client.get("/temperature")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["timestamp"], int)
    assert isinstance(data["value"], float)
    assert data["status"] in ["Good", "Too Cold", "Too Hot"]

def test_get_temperature_stale_data(mocker, mock_sensor_responses_stale):
    """Test temperature endpoint properly handles stale sensor data."""
    mock_get = mocker.patch('requests.get')
    mock_get.return_value.json.side_effect = [
        mock_sensor_responses_stale["tempSensor01"],
        mock_sensor_responses_stale["tempSensor02"],
        mock_sensor_responses_stale["tempSensor03"]
    ]

    response = client.get("/temperature")
    assert response.status_code == 500
    assert response.json()["detail"] == "All available readings are over 1 hour old"

def test_get_temperature_invalid_json(mocker):
    """Test temperature endpoint handles invalid JSON responses."""
    mock_get = mocker.patch('requests.get')
    mock_get.return_value.json.side_effect = ValueError("Invalid JSON")

    response = client.get("/temperature")
    assert response.status_code == 500
    assert "Invalid data received" in response.json()["detail"]

def test_get_temperature_invalid_value(mocker, mock_sensor_responses_invalid_value):
    """Test temperature endpoint handles non-numeric temperature values."""
    mock_get = mocker.patch('requests.get')
    mock_get.return_value.json.return_value = mock_sensor_responses_invalid_value["tempSensor01"]

    response = client.get("/temperature")
    assert response.status_code == 500
    assert "Invalid data received" in response.json()["detail"]

def test_get_temperature_network_error(mocker):
    """Test temperature endpoint handles network request failures."""
    mock_get = mocker.patch('requests.get')
    mock_get.side_effect = requests.RequestException("Connection error")

    response = client.get("/temperature")
    assert response.status_code == 500
    assert "Failed to fetch data" in response.json()["detail"]

def test_metrics():
    """Test that metrics endpoint returns proper Prometheus format."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert isinstance(response.text, str)
