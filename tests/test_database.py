from dataclasses import FrozenInstanceError
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.database import build_index
from src.database.normalizer import CATEGORIES, normalize_key, strip_prefix
from src.database.trie import WordTrie


ROOT = Path(__file__).resolve().parents[1]
SEARCH_ROOT = ROOT / "clone" / "Address-Segmentation--Advanced-Algorithm--Project--HCMUT-feature-searching"


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def write(self, name, text):
        (self.directory / name).write_text(text, encoding="utf-8-sig")

    def test_txt_normalization_duplicates_collisions_and_categories(self):
        self.write("streets.txt", "Đường Mới\nDuong Moi\nĐường Mới\n\nĐường 3/2\nQuang Trung\n")
        self.write("wards.txt", "Phường Tân Phú\nXã Tân Phú\nQuang Trung\n")
        self.write("provinces.txt", "Hồ Chí Minh\n")
        index = build_index(self.directory)
        self.assertEqual(index.exact_lookup("street", "duong moi"), ["Đường Mới", "Duong Moi"])
        self.assertEqual(index.exact_lookup("street", "Đ. 3 / 2"), ["Đường 3/2"])
        self.assertEqual(index.exact_lookup("ward", "tan phu"), ["Phường Tân Phú", "Xã Tân Phú"])
        self.assertEqual(index.exact_lookup("province", "Quang Trung"), [])
        self.assertEqual(index.exact_lookup("street", "DuongMoi"), ["Đường Mới", "Duong Moi"])
        self.assertEqual(index.exact_lookup("street", "duong moii"), [])
        self.assertEqual(index.exact_lookup("street", ""), [])
        self.assertEqual(index.stats()["counts"], {"street": 4, "ward": 3, "province": 1})
        self.assertEqual(normalize_key("Đ. 3 / 2 - A_B"), "d 3/2 a b")

    def test_prefix_is_whole_word_unique_and_bounded(self):
        self.write("streets.txt", "Nguyễn Thị Minh Khai\nNguyễn Thị Định\n")
        self.write("aliases.json", json.dumps({"street": {"Nguyễn Thị Minh Khai": ["nguyen thi minh khai extended"]}}))
        index = build_index(self.directory)
        self.assertEqual(index.prefix_lookup("street", "nguyen thi"), ["Nguyễn Thị Minh Khai", "Nguyễn Thị Định"])
        self.assertEqual(index.prefix_lookup("street", "nguyen thi", 1), ["Nguyễn Thị Minh Khai"])
        self.assertEqual(index.prefix_lookup("street", "nguy"), [])
        self.assertEqual(index.prefix_lookup("street", "", 10), [])
        self.assertEqual(index.prefix_lookup("street", "nguyen", 0), [])
        self.assertEqual(index.prefix_lookup("street", "nguyen", -1), [])

    def test_alias_collisions_keep_only_loaded_targets(self):
        self.write("provinces.txt", "Hồ Chí Minh\nHà Nội\n")
        self.write("aliases.json", json.dumps({"province": {
            "Hồ Chí Minh": ["TP HCM", "shared", "TP HCM"],
            "Hà Nội": ["shared"], "Missing": ["invented"]}}))
        index = build_index(self.directory)
        self.assertEqual(index.exact_lookup("province", "tphcm"), ["Hồ Chí Minh"])
        self.assertEqual(index.exact_lookup("province", "shared"), ["Hồ Chí Minh", "Hà Nội"])
        self.assertEqual(index.exact_lookup("province", "invented"), [])
        self.assertNotIn("Missing", index.aliases["province"])

    def test_no_alias_invented_or_canonical_prefix_rewritten(self):
        self.write("province.csv", "canonical\nThành phố Hồ Chí Minh\n")
        index = build_index(self.directory)
        self.assertEqual(index.exact_lookup("province", "Ho Chi Minh"), ["Thành phố Hồ Chí Minh"])
        self.assertEqual(index.exact_lookup("province", "TP HCM"), [])
        self.assertTrue(index.contains_canonical("Thành phố Hồ Chí Minh", "province"))
        self.assertFalse(index.contains_canonical("Ho Chi Minh"))

    def test_csv_combined_with_quoted_multiline_and_blank_cells(self):
        self.write("sample.csv", 'ID,text,province,ward,street\n1,"OCR,\ntext",Hà Nội,,An Dương\n2,text,,Bến Thành,\n')
        index = build_index(self.directory)
        self.assertEqual(index.stats()["total_entries"], 3)
        self.assertEqual(index.exact_lookup("street", "Ngách 32/36 Phố An Dương"), ["An Dương"])
        self.assertEqual(index.exact_lookup("ward", "p ben thanh"), ["Bến Thành"])

    def test_json_and_jsonl_formats(self):
        self.write("streets.json", json.dumps(["3/2", {"canonical": "An Dương"}]))
        self.write("records.jsonl", '\n' + json.dumps({"category": "ward", "name": "Bến Thành"}) + '\n')
        self.write("records.json", json.dumps({"provinces": ["Hà Nội"], "street": None}))
        index = build_index(self.directory)
        self.assertEqual(index.stats()["total_entries"], 4)
        self.assertEqual(index.exact_lookup("street", "3/2"), ["3/2"])
        self.assertEqual(index.exact_lookup("ward", "ben thanh"), ["Bến Thành"])

    def test_invalid_inputs_fail_clearly(self):
        with self.assertRaises(FileNotFoundError):
            build_index(self.directory / "missing")
        with self.assertRaises(ValueError):
            build_index(self.directory)
        for name, content in (
            ("street.csv", "wrong\nName\n"),
            ("sample.csv", "street,ward\nName\n"),
            ("sample.csv", "street\nName,extra\n"),
            ("streets.txt", "---\n"),
            ("records.jsonl", '{"category": "district", "name": "X"}'),
            ("records.json", '{"province": 42}'),
            ("records.json", '{"category": "province"}'),
        ):
            with self.subTest(name=name, content=content):
                self.write(name, content)
                with self.assertRaises(ValueError):
                    build_index(self.directory)
                (self.directory / name).unlink()
        self.write("streets.txt", "An Dương\n")
        for payload in ([], {"street": {"An Dương": "AD"}}, {"district": {}}):
            self.write("aliases.json", json.dumps(payload))
            with self.assertRaises(ValueError):
                build_index(self.directory)

    def test_read_only_snapshot_and_detached_results(self):
        self.write("streets.txt", "An Dương\n")
        index = build_index(self.directory)
        self.write("streets.txt", "Changed\n")
        self.assertEqual(index.exact_lookup("street", "An Duong"), ["An Dương"])
        result = index.exact_lookup("street", "An Duong")
        result.clear()
        self.assertEqual(index.exact_lookup("street", "An Duong"), ["An Dương"])
        with self.assertRaises(TypeError):
            index.tries["street"] = None
        with self.assertRaises(TypeError):
            index.tries["street"]._root.children["new"] = None
        with self.assertRaises(FrozenInstanceError):
            index.tries["street"]._root.canonical = ()
        with self.assertRaises(FrozenInstanceError):
            index.entries("street")[0].canonical = "Changed"
        with self.assertRaises(TypeError):
            index.aliases["street"]["An Dương"] = ("AD",)
        for call in (
            lambda: index.exact_lookup("district", "X"),
            lambda: index.prefix_lookup("district", "X"),
            lambda: index.entries("district"),
            lambda: index.contains_canonical("X", "district"),
        ):
            with self.assertRaises(ValueError):
                call()
        with self.assertRaises(TypeError):
            normalize_key(1)

    def test_long_token_path_does_not_require_recursion(self):
        key = " ".join(f"word{i}" for i in range(1500))
        trie = WordTrie.from_pairs([(key, "Canonical"), (key, "Canonical")])
        self.assertEqual(trie.exact(key), ["Canonical"])
        self.assertEqual(trie.prefix("word0"), ["Canonical"])

    def test_main_reuses_real_index(self):
        from src.main import run_pipeline

        self.write("streets.txt", "An Dương\n")
        observed = []

        def segment(raw):
            return {"raw_address": raw, "spans": [{"field": "street", "text": raw}]}

        def search(segmented, index):
            observed.append(index)
            matches = index.exact_lookup("street", segmented["spans"][0]["text"])
            return {"street": matches[0] if len(matches) == 1 else None, "ward": None, "province": None}

        output = io.StringIO()
        with patch("src.main._load_teammate_functions", return_value=(build_index, segment, search)):
            run_pipeline(["An Duong", "unknown"], self.directory, output)
        self.assertIs(observed[0], observed[1])
        self.assertEqual([json.loads(line)["street"] for line in output.getvalue().splitlines()], ["An Dương", None])


@unittest.skipUnless((SEARCH_ROOT / "src/searching/dictionary.py").is_file(), "Searching reference clone is unavailable")
class SearchingCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("_searching_reference", SEARCH_ROOT / "src/searching/dictionary.py")
        cls.reference = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.reference
        spec.loader.exec_module(cls.reference)
        cls.index = build_index(SEARCH_ROOT / "data")
        cls.dictionary = cls.reference.AddressDictionary.from_directory(SEARCH_ROOT / "data")

    def test_same_canonical_entries_and_normalized_keys(self):
        for category in CATEGORIES:
            self.assertEqual(
                [(e.canonical, e.category, e.normalized) for e in self.index.entries(category)],
                [(e.canonical, e.category, e.normalized) for e in self.dictionary.entries(category)],
            )

    def test_exact_matches_agree_for_all_canonical_names_and_aliases(self):
        for category in CATEGORIES:
            queries = [entry.canonical for entry in self.index.entries(category)]
            queries += [alias for values in self.index.aliases[category].values() for alias in values]
            queries += ["P1", "D3/2", "QL1A", "Ngách 32/36 Phố An Dương", "Hẻm e Cách Mạng Tháng 8", "TP.HCM", "T.P. Ha Noi", "", "unknown"]
            for query in queries:
                for variant in (query, normalize_key(query), normalize_key(query).replace(" ", "")):
                    with self.subTest(category=category, query=variant):
                        self.assertEqual(self.index.exact_lookup(category, variant), [m.canonical for m in self.dictionary.lookup_exact(variant, category)])
                        self.assertEqual(normalize_key(variant), self.reference.normalize_text(variant))
                        self.assertEqual(strip_prefix(normalize_key(variant), category), self.reference.strip_prefix(normalize_key(variant), category))

    def test_existing_fuzzy_search_can_consume_index_entries_without_reading_files(self):
        dictionary = self.reference.AddressDictionary(
            {cat: self.index.entries(cat) for cat in CATEGORIES}, aliases=self.index.aliases
        )
        for query, category in (("Pastuer", "street"), ("Cáiể Kế", "ward"), ("KháMh Hòa", "province"), ("TP HCM", "province")):
            self.assertEqual(dictionary.find_best(query, category), self.dictionary.find_best(query, category))


if __name__ == "__main__":
    unittest.main()
