"""Hivebox package configuration and shared utilities."""

__version__ = "0.4.0"

SENSEBOX_TEMP_SENSORS = {
    '62abdbfbb91502001b7c05a8': '62abdbfbb91502001b7c05ab',
    '6351780cc18329001ba8d4a3': '6351780cc18329001ba8d4a6',
    '63ac947f1aaa3a001b8a34bd': '63ac947f1aaa3a001b8a34bf'
}

FORMAT = 'json'

def get_sensor_data(box_id, sensor_id):
    """Generate API URL to retrieve temperature for given senseBox."""
    return f'https://api.opensensemap.org/boxes/{box_id}/sensors/{sensor_id}'
