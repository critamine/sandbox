"""Test suite for main API endpoints."""

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_get_version():
    """Test version endpoint returns correct format and status."""
    response = client.get("/version")
    assert response.status_code == 200
    assert "hivebox" in response.json()
    assert isinstance(response.json()["hivebox"], str)

def test_get_temperature(mocker):
    """Test temperature endpoint with mocked sensor data."""
    mock_return_value = {
        "temperature": 21,
        "status": "Good"  
    }
    mocker.patch('main.get_average_temperature', return_value=mock_return_value)
    response = client.get("/temperature")
    assert response.status_code == 200
    assert "temperature" in response.json()
    assert "status" in response.json()
    assert response.json()["temperature"] == 21
    assert response.json()["status"] == "Good"
