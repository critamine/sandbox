"""Fuzzer for temperature module's sensor data parsing."""
# pylint: disable=broad-except,protected-access,duplicate-code

import sys
import json
import atheris
from hivebox.temperature import TemperatureService

@atheris.instrument_func
def test_one_input(data):
    """Fuzz test the sensor data parsing with malformed JSON responses."""
    if len(data) < 1:
        return

    service = TemperatureService({"test_box": "test_sensor"})

    try:
        fuzz_dict = {
            "lastMeasurement": {
                "createdAt": atheris.FuzzedDataProvider(data).ConsumeString(30),
                "value": atheris.FuzzedDataProvider(data).ConsumeFloat(),
            }
        }
        mock_response = json.dumps(fuzz_dict)

        class MockResponse:
            def json(self):
                return json.loads(mock_response)

        service._process_sensor_reading(MockResponse(), "test_sensor")
    except Exception:
        pass

def main():
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()

if __name__ == "__main__":
    main()
