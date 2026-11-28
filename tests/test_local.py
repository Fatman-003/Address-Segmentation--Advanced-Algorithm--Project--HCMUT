import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.address_segmentation import segment_address

DATA_FILE = ROOT_DIR / "src" / "address_segmentation" / "test_data.json"


def run_tests():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
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
        else:
            print(f"[FAIL] Case {idx}: {name}")

        print(f"  Input   : {raw_input!r}")
        print(f"  Expected: {expected}")
        print(f"  Actual  : {actual}")
        print("-" * 50)

    print(f"\nResult: {passed}/{total} PASSED.")


if __name__ == "__main__":
    run_tests()