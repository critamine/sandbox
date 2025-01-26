#!/usr/bin/python3

"""Fuzzing script for testing the avg_data function from hivebox.temperature."""

import sys
import atheris
from hivebox.temperature import avg_data

def test_one_input(data):
    """Test the avg_data function with fuzzed input."""
    fdp = atheris.FuzzedDataProvider(data)
    num_boxes = fdp.ConsumeIntInRange(0, 5)  
    test_data = {}

    try:
        for _ in range(num_boxes):
            box_id = fdp.ConsumeString(10)
            temp_value = str(fdp.ConsumeFloat())
            test_data[box_id] = {
                'last': {
                    'value': temp_value
                }
            }

        avg_data(test_data)
        return

    except ZeroDivisionError:
        return
    except Exception:
        return

def main():
    """Set up and run the fuzzer."""
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()

if __name__ == "__main__":
    main()
