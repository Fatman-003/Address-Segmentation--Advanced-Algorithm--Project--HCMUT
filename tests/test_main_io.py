import io
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.main import ModuleNotReadyError, read_addresses, run_pipeline, validate_output, write_result


class TestMainIO(unittest.TestCase):
    def test_read_preserves_content(self):
        s = io.StringIO(" 53 Nguyễn Trãi, P. 1 \n\n3/2\n")
        self.assertEqual(list(read_addresses(s)), [" 53 Nguyễn Trãi, P. 1 ", "", "3/2"])

    def test_jsonl_output_utf8_and_null(self):
        buffer = io.StringIO()
        write_result(buffer, {"street": "Đường 3/2", "ward": None, "province": "Hà Nội"})
        self.assertEqual(json.loads(buffer.getvalue()), {
            "street": "Đường 3/2", "ward": None, "province": "Hà Nội"
        })
        self.assertIn("Đường", buffer.getvalue())

    def test_reject_missing_or_extra_fields(self):
        with self.assertRaises(ValueError):
            validate_output({"street": "a", "ward": None})
        with self.assertRaises(ValueError):
            validate_output({"street": None, "ward": None, "province": None, "x": 1})

    def test_reject_wrong_value_type(self):
        with self.assertRaises(TypeError):
            validate_output({"street": ["a"], "ward": None, "province": None})

    def test_orchestration_builds_once_and_processes_each_address(self):
        index = object()
        build_index = Mock(return_value=index)
        segment_address = Mock(side_effect=lambda raw: {"raw_address": raw, "spans": []})
        search_address = Mock(return_value={"street": None, "ward": None, "province": None})
        out = io.StringIO()
        with patch("src.main._load_teammate_functions", return_value=(
            build_index, segment_address, search_address
        )):
            run_pipeline(["address 1", "address 2"], Path("data"), out)
        build_index.assert_called_once_with(Path("data"))
        self.assertEqual(segment_address.call_count, 2)
        self.assertEqual(search_address.call_count, 2)
        self.assertIs(search_address.call_args_list[0].args[1], index)
        self.assertIs(search_address.call_args_list[1].args[1], index)
        self.assertEqual(len(out.getvalue().splitlines()), 2)

        with self.assertRaises(ModuleNotReadyError):
            run_pipeline(["53 Nguyen Trai"], Path("data"), io.StringIO())


if __name__ == "__main__":
    unittest.main()
