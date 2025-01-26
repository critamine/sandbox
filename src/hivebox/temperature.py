"""Temperature data processing module."""

from datetime import datetime, timedelta, timezone
import requests
from . import SENSE_BOX_IDS, get_url

def fetch_data():
    """Fetch raw temperature data from all sensor boxes."""
    timeout = 10  # seconds
    return {
        sense_box_id: requests.get(get_url(sense_box_id), timeout=timeout).json()
        if requests.get(get_url(sense_box_id), timeout=timeout).status_code == 200
        else f"Error: {requests.get(get_url(sense_box_id), timeout=timeout).status_code}"
        for sense_box_id in SENSE_BOX_IDS
    }

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
        return None

def get_temperature_status(averaged_result: int) -> str:
    """Returns a temperature status string based on input value"""
    if averaged_result is None:
        return "No Data"
    if averaged_result <= 10:
        return "Too Cold"
    if averaged_result <= 36:
        return "Good"
    return "Too Hot"

def get_average_temperature():
    """Get current average temperature from all valid sensors."""
    result = fetch_data()
    trimmed_result = trim_data(result)
    validated_result = validate_data(trimmed_result)
    averaged_result = avg_data(validated_result)
    temperature_status = get_temperature_status(averaged_result)
    return {
        "temperature": averaged_result,
        "status": temperature_status
    }
