"""Temperature data processing module."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict
import requests
from . import get_sensorData


class TemperatureServiceError(Exception):
    """Raised when temperature service operations fail."""
    pass


@dataclass
class SensorReading:
    """Single temperature sensor reading with ID, value, and timestamp."""
    sensor_id: str
    value: float
    timestamp: datetime


@dataclass
class TemperatureResult:
    """Final averaged temperature with status for API response."""
    value: float
    status: str


class TemperatureService:
    """Service for processing temperature data from sensors."""

    def __init__(self, sensor_data: Dict[str, str]):
        """Initialize temperature service with sensor data mapping."""
        if not sensor_data:
            raise TemperatureServiceError("No sensor data provided")
        self.sensor_data = sensor_data

    def get_average_temperature(self) -> TemperatureResult:
        """Calculate and return average temperature from all sensor readings."""
        readings = self._fetch_readings()
        if not readings:
            raise TemperatureServiceError("No readings available")

        avg_temp = round(sum(r.value for r in readings) / len(readings), 1)
        status = self._determine_temperature_status(avg_temp)

        return TemperatureResult(value=avg_temp, status=status)

    def _fetch_readings(self) -> List[SensorReading]:
        """Fetch current readings from all sensors that are less than 1 hour old."""
        readings = []
        current_time = datetime.now(timezone.utc)

        for box_id, sensor_id in self.sensor_data.items():
            url = get_sensorData(box_id, sensor_id)
            try:
                response = requests.get(url, timeout=30)
                data = response.json()
                reading_time = datetime.fromisoformat(
                    data['lastMeasurement']['createdAt'].replace('Z', '+00:00'))
                time_diff = current_time - reading_time

                if time_diff.total_seconds() > 3600:
                    continue

                reading = SensorReading(
                    timestamp=reading_time,
                    value=float(data['lastMeasurement']['value']),
                    sensor_id=sensor_id)
                readings.append(reading)

            except requests.RequestException as e:
                raise TemperatureServiceError(
                    f"Failed to fetch data for sensor {sensor_id}: {str(e)}") from e
            except ValueError as e:
                raise TemperatureServiceError(
                    f"Invalid data received from sensor {sensor_id}: {str(e)}") from e

        if not readings:
            raise TemperatureServiceError("All available readings are over 1 hour old")

        return readings

    def _determine_temperature_status(self, temperature: float) -> str:
        """Return temperature status based on provided value."""
        if not isinstance(temperature, (int, float)):
            raise TemperatureServiceError(f"Invalid temperature value: {temperature}")

        if temperature <= 10:
            return "Too Cold"
        if temperature <= 36:
            return "Good"
        return "Too Hot"
