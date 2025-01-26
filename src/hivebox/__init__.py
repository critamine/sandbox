"""Hivebox package configuration and shared utilities."""

__version__ = "0.2.0"

SENSE_BOX_IDS = [
    '62abdbfbb91502001b7c05a8',
    '6351780cc18329001ba8d4a3',
    '63ac947f1aaa3a001b8a34bd'
]

FORMAT = 'json'

def get_url(sense_box_id):
    """Generate API URL for a given sensor box ID."""
    return f'https://api.opensensemap.org/boxes/{sense_box_id}?format={FORMAT}'
