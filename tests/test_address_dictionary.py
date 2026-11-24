import json
from pathlib import Path
import tempfile
import time
import unittest

from src.searching.dictionary import (
    CATEGORIES,
    AddressDictionary,
    edit_distance,
    edit_similarity,
    normalize_text,
    remove_vietnamese_diacritics,
    strip_prefix,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"


class TestNormalizationAndSimilarity(unittest.TestCase):
    def test_normalization_and_prefix_stripping(self):
        self.assertEqual(remove_vietnamese_diacritics("Đường 3/2"), "Duong 3/2")
        self.assertEqual(normalize_text("  Thành phố Hà Nội,  "), "thanh pho ha noi")
        self.assertEqual(normalize_text("Đ. 3 / 2"), "d 3/2")
        self.assertEqual(strip_prefix("ngach 32/36 pho an duong", "street"), "an duong")
        self.assertEqual(strip_prefix("ngo so 3 duong le thanh tong", "street"), "le thanh tong")
        self.assertEqual(strip_prefix("pham ngu lao", "ward"), "pham ngu lao")
        self.assertEqual(strip_prefix("ngo tram", "street"), "ngo tram")

    def test_similarity_metrics(self):
        self.assertEqual(edit_distance("ha noi", "ha noi"), 0)
        self.assertEqual(edit_distance("khanh hoa", "khamh hoa"), 1)
        self.assertEqual(edit_similarity("ha noi", "ha noi"), 1.0)
        self.assertEqual(edit_similarity("", ""), 0.0)
        self.assertGreater(edit_similarity("khanh hoa", "khamh hoa"), 0.85)


class TestAddressDictionary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dictionary = AddressDictionary.from_directory(DATA_DIR)

    def test_loads_three_canonical_classes(self):
        counts = self.dictionary.stats()["counts"]
        self.assertEqual(counts["province"], 64)
        self.assertGreaterEqual(counts["ward"], 350)
        self.assertGreaterEqual(counts["street"], 230)
        for cat in CATEGORIES:
            self.assertTrue(all(e.canonical for e in self.dictionary.entries(cat)))

        self.assertTrue(self.dictionary.contains_canonical("Hà Nội", "province"))
        self.assertTrue(self.dictionary.contains_canonical("Bình Dương", "province"))
        self.assertTrue(self.dictionary.contains_canonical("Hiệp Bình Chánh", "ward"))
        self.assertTrue(self.dictionary.contains_canonical("An Dương", "street"))

    def test_exact_and_alias_lookup(self):
        cases = [
            ("Ngách 32/36 Phố An Dương", "street", "An Dương"),
            ("Hom 70 Trần Hưng Đạo", "street", "Trần Hưng Đạo"),
            ("Hẻm e Cách Mạng Tháng 8", "street", "Cách Mạng Tháng 8"),
            ("Hẻm 55/19/14 Phố Gia Thượng", "street", "Gia Thượng"),
            ("Ngõ Số 3 Đường Lê Thánh Tông", "street", "Lê Thánh Tông"),
            ("Ngõ 97 Đường Gia Thượng", "street", "Gia Thượng"),
            ("D3/2", "street", "3/2"),
            ("3 thang 2", "street", "3/2"),
            ("QL1A", "street", "Quốc lộ 1A"),
            ("CMT8", "street", "Cách Mạng Tháng 8"),
            ("Xã Nghĩa Trụ", "ward", "Nghĩa Trụ"),
            ("Phường Hiệp Bình Chánh", "ward", "Hiệp Bình Chánh"),
            ("Phường Phường Đúc", "ward", "Phường Đúc"),
            ("P. 28", "ward", "28"),
            ("P1", "ward", "1"),
            ("Thành phố Hà Nội", "province", "Hà Nội"),
            ("Tỉnh Bình Dương", "province", "Bình Dương"),
            ("TTH", "province", "Thừa Thiên Huế"),
            ("BRVT", "province", "Bà Rịa - Vũng Tàu"),
            ("TP.HCM", "province", "Hồ Chí Minh"),
            ("HoChiMinh", "province", "Hồ Chí Minh"),
        ]
        for query, cat, expected in cases:
            with self.subTest(query=query, category=cat):
                canonicals = {m.canonical for m in self.dictionary.lookup_exact(query, cat)}
                self.assertIn(expected, canonicals)

    def test_preserves_collisions(self):
        custom = AddressDictionary.from_lists(
            wards=("Phường Tân Phú", "Xã Tân Phú"),
            streets=("Đường 3/2", "3/2"),
        )
        self.assertEqual(
            {m.canonical for m in custom.lookup_exact("Tân Phú", "ward")},
            {"Phường Tân Phú", "Xã Tân Phú"},
        )
        self.assertEqual(
            {m.canonical for m in custom.lookup_exact("3/2", "street")},
            {"Đường 3/2", "3/2"},
        )
        cross_class = {(m.category, m.canonical) for m in self.dictionary.lookup_exact("Quang Trung")}
        self.assertIn(("ward", "Quang Trung"), cross_class)
        self.assertIn(("street", "Quang Trung"), cross_class)

    def test_find_best_picks_highest_similarity_for_noisy_ocr(self):
        noisy_cases = [
            ("TrầnDHưng Đạo", "street", "Trần Hưng Đạo"),
            ("Nguyễn Lương Bỳng", "street", "Nguyễn Lương Bằng"),
            ("Lộ Triền eĐồng", "street", "Lộ Triền Đồng"),
            ("ặng Dèng", "street", "Đặng Dung"),
            ("Cô Giỵang", "street", "Cô Giang"),
            ("Cáiể Kế", "ward", "Cái Khế"),
            ("Đoàn uKế", "ward", "Đoàn Kết"),
            ("Móng Ci ổ", "ward", "Móng Cái 2"),
            ("KháMh Hòa", "province", "Khánh Hòa"),
            ("Hảiự Phòng", "province", "Hải Phòng"),
            ("Pastuer", "street", "Pasteur"),
        ]
        for query, cat, expected in noisy_cases:
            with self.subTest(query=query, category=cat):
                best = self.dictionary.find_best(query, cat, threshold=0.5)
                self.assertIsNotNone(best)
                self.assertEqual(best.canonical, expected)  # type: ignore[union-attr]

    def test_threshold_rejects_unrelated_input(self):
        self.assertIsNone(self.dictionary.find_best("XYZ12345", "street", threshold=0.6))
        self.assertEqual(self.dictionary.search("XYZ12345", "ward", threshold=0.7), [])

    def test_latency_within_budget(self):
        queries = [
            ("Nguyen Thi Minh Khai", "street"),
            ("P Ben Thanh", "ward"),
            ("TP HCM", "province"),
            ("Cáiể Kế", "ward"),
            ("KháMh Hòa", "province"),
        ]
        start = time.perf_counter()
        iterations = 40
        for _ in range(iterations):
            for q, cat in queries:
                self.dictionary.find_best(q, cat, threshold=0.5)
        mean_seconds = (time.perf_counter() - start) / (iterations * len(queries))
        self.assertLess(mean_seconds, 0.01)


class TestFlexibleLoading(unittest.TestCase):
    def test_loads_csv_sample_schema_with_blank_cells(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "sample.csv").write_text(
                "ID,text,province,ward,street\n"
                '0,"Ngách 32/36 hố An Dương, Phường Hồng Hà, ễThành phố Hà Nội",Hà Nội,,An Dương\n'
                '1,"Phố Tâyớ4, Xã Nghĩi rụ, Tinh õưng Yên",Hưng Yên,Nghĩa Trụ,Tây 4\n'
                '3,"Đường Lê Ngọ Hân, Phường Vinh Phú, Tinh NghệAn",,,\n',
                encoding="utf-8",
            )
            loaded = AddressDictionary.from_directory(root)
            self.assertTrue(loaded.contains_canonical("Hà Nội", "province"))
            self.assertTrue(loaded.contains_canonical("Nghĩa Trụ", "ward"))
            self.assertTrue(loaded.contains_canonical("An Dương", "street"))
            self.assertFalse(loaded.contains_canonical("Hồ Chí Minh", "province"))

    def test_ignores_aliases_not_in_loaded_database(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "provinces.txt").write_text("Gamma\n", encoding="utf-8")
            (root / "aliases.json").write_text(
                json.dumps({"province": {"Gamma": ["gm"], "Hồ Chí Minh": ["hcm"]}}),
                encoding="utf-8",
            )
            loaded = AddressDictionary.from_directory(root)
            self.assertEqual(loaded.lookup_exact("hcm", "province"), [])
            self.assertEqual(loaded.find_best("gm", "province").canonical, "Gamma")  # type: ignore[union-attr]

    def test_missing_or_empty_directory_raises_error(self):
        with self.assertRaises(FileNotFoundError):
            AddressDictionary.from_directory(Path("/nonexistent/database_dir"))
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ValueError):
                AddressDictionary.from_directory(Path(tmpdir))


if __name__ == "__main__":
    unittest.main()
