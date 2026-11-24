import json
from pathlib import Path
from address_segmentation import segment_address
import sys

sys.stdout.reconfigure(encoding="utf-8")

def run_tests():
    # Lấy đường dẫn tuyệt đối tới file test_data.json nằm cùng thư mục
    current_dir = Path(__file__).parent
    data_file = current_dir / "test_data.json"

    with open(data_file, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    passed = 0
    total = len(test_cases)

    print(f"=== Start {total} TEST CASES ===\n")

    for idx, case in enumerate(test_cases, start=1):
        name = case["name"]
        raw_input = case["input"]
        expected = case["expected_spans"]

        result = segment_address(raw_input)
        actual = result["spans"]

        if actual == expected:
            passed += 1
            print(f"[PASS] Case {idx}: {name}")
            print(f"  Input   : {raw_input!r}")
            print(f"  Expected: {expected}")
            print(f"  Actual  : {actual}")
        else:
            print(f"[FAIL] Case {idx}: {name}")
            print(f"  Input   : {raw_input!r}")
            print(f"  Expected: {expected}")
            print(f"  Actual  : {actual}")
        print("-" * 50)

    print(f"\nResult: {passed}/{total} PASSED.")


if __name__ == "__main__":
    run_tests()