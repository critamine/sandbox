"""Temperature data processing module."""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict
import requests
from .metrics import (
    OPENSENSEMAP_CALLS,
    OPENSENSEMAP_LATENCY,
    OPENSENSEMAP_AGE,
    UNREACHABLE_SENSORS,
    TEMPERATURE_SENSORS_USED,
)
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TemperatureServiceError(Exception):
    """Raised when temperature service operations fail."""


@dataclass
class SensorReading:
    """Single temperature sensor reading with ID, value, and timestamp."""
    sensor_id: str
    value: float
    timestamp: datetime


class TemperatureResult(BaseModel):
    """Final averaged temperature with status for API response."""
    value: float
    status: str
    timestamp: int

def sensor_url(base_url: str, box_id: str, sensor_id: str) -> str:
    """Build the full endpoint for a given senseBox sensor"""
    return f"{base_url}boxes/{box_id}/sensors/{sensor_id}"


# pylint: disable=too-few-public-methods
class TemperatureService:
    """Service for processing temperature data from sensors."""

    def __init__(
            self,
            osm_base_url: str,
            sensor_map: Dict[str, str]
        ):
        """Initialize temperature service with sensor data mapping."""
        if not sensor_map:
            raise TemperatureServiceError("No sensor data provided")
        self.osm_base_url = osm_base_url
        self.sensor_map = sensor_map

    def get_average_temperature(self, mode: str) -> TemperatureResult:
        """Calculate and return average temperature from all sensor readings."""
        readings = self._fetch_readings(mode)
        TEMPERATURE_SENSORS_USED.set(len(readings))
               
        avg_temp = round(sum(r.value for r in readings) / len(readings), 1)
        status = self._determine_temperature_status(avg_temp)
        computed_at = int(datetime.now(timezone.utc).timestamp())

        return TemperatureResult(value=avg_temp, status=status, timestamp=computed_at)

    def _fetch_readings(self, mode: str) -> List[SensorReading]:
        """
        Fetch current readings from all sensors that are less than 1 hour old.
        This method is resilient and will continue even if some sensors fail.
        """
        readings: List[SensorReading] = []
        unreachable_count = 0
        current_time = datetime.now(timezone.utc)

        try: # pylint: disable=too-many-nested-blocks
            for box_id, sensor_id in self.sensor_map.items():
                url = sensor_url(self.osm_base_url, box_id, sensor_id)
                start_time = time.time()
                try:
                    resp = requests.get(url, timeout=30)
                    resp.raise_for_status()
                    data = resp.json()
                    reading_time = datetime.fromisoformat(
                        data['lastMeasurement']['createdAt'].replace('Z', '+00:00'))
                    time_diff = current_time - reading_time

                    OPENSENSEMAP_AGE.labels(
                        sensebox_id=box_id).observe(
                            time_diff.total_seconds()
                    )

                    if time_diff.total_seconds() > 3600:
                        OPENSENSEMAP_CALLS.labels(
                            sensebox_id=box_id, result="stale", mode=mode).inc()
                        unreachable_count += 1
                        continue

                    OPENSENSEMAP_CALLS.labels(
                        sensebox_id=box_id, result="success", mode=mode).inc()

                    reading = SensorReading(
                        timestamp=reading_time,
                        value=float(data['lastMeasurement']['value']),
                        sensor_id=sensor_id)
                    readings.append(reading)

                except (requests.RequestException, ValueError, KeyError) as e:
                    logger.warning("Failed to get reading for sensor %s: %s", sensor_id, e)
                    OPENSENSEMAP_CALLS.labels(
                        sensebox_id=box_id, result="error", mode=mode).inc()
                    unreachable_count += 1

                finally:
                    latency = time.time() - start_time
                    OPENSENSEMAP_LATENCY.labels(sensebox_id=box_id).observe(latency)

            if not readings:
                raise TemperatureServiceError("No valid sensor readings could be fetched")

            return readings
        finally:
            UNREACHABLE_SENSORS.set(unreachable_count)

    def _determine_temperature_status(self, temperature: float) -> str:
        """Return temperature status based on provided value."""
        if not isinstance(temperature, (int, float)):
            raise TemperatureServiceError(f"Invalid temperature value: {temperature}")

        if temperature <= 10:
            return "Too Cold"
        if temperature <= 36:
            return "Good"
        return "Too Hot"
