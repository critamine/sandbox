#!/usr/bin/python3

import atheris
import sys
from hivebox.temperature import avg_data

def TestOneInput(data):
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
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()

if __name__ == "__main__":
    main()
