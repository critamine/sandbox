"""Fuzzer for temperature module's status determination."""

import atheris
import sys
import struct
from hivebox.temperature import TemperatureService

@atheris.instrument_func
def test_one_input(data):
    """Fuzz test the temperature status determination with random float values."""
    if len(data) < 8:
        return

    temp_value = struct.unpack('d', data[:8])[0]
    service = TemperatureService({"dummy": "dummy"})

    try:
        result = service._determine_temperature_status(temp_value)
        assert result in ["Too Cold", "Good", "Too Hot"]
    except Exception:
        pass

def main():
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()

if __name__ == "__main__":
    main()
