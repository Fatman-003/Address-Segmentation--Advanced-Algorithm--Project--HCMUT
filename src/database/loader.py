from __future__ import annotations

import csv
import json
from pathlib import Path

from .normalizer import CATEGORIES, Category, normalize_key


FIELDS = CATEGORIES
_FILE_STEMS = {
    "street": ("street", "streets", "duong"),
    "ward": ("ward", "wards", "phuong", "xa"),
    "province": ("province", "provinces", "tinh"),
}


def _file_category(path: Path) -> Category | None:
    stem = normalize_key(path.stem)
    return next((cat for cat in CATEGORIES if stem in _FILE_STEMS[cat]), None)


def _add(buckets: dict[Category, list[str]], category: Category, value: object, context: str) -> None:
    if value is None or value == "":
        return
    if not isinstance(value, str):
        raise ValueError(f"{context}: canonical value must be a string")
    canonical = value.strip()
    if not canonical:
        return
    if not normalize_key(canonical):
        raise ValueError(f"{context}: canonical value has an empty search key")
    buckets[category].append(canonical)


def _read_csv(path: Path, buckets: dict[Category, list[str]]) -> None:
    category = _file_category(path)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = {normalize_key(name): name for name in reader.fieldnames or ()}
        targets = [(cat, columns[key]) for cat in CATEGORIES for key in (cat, f"{cat}s") if key in columns]
        if not targets and category is not None:
            column = columns.get("canonical") or columns.get("name")
            if column is not None:
                targets = [(category, column)]
        if not targets:
            raise ValueError(f"{path}: expected street/ward/province columns or a category CSV with canonical/name")
        for row in reader:
            context = f"{path}:{reader.line_num}"
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{context}: row does not match CSV header")
            for cat, column in targets:
                _add(buckets, cat, row[column], context)


def _read_record(record: object, buckets: dict[Category, list[str]], context: str, category: Category | None) -> None:
    if isinstance(record, str) and category is not None:
        _add(buckets, category, record, context)
        return
    if not isinstance(record, dict):
        raise ValueError(f"{context}: expected an address object or a string in a category file")
    recognized = False
    for cat in CATEGORIES:
        for key in (cat, f"{cat}s"):
            if key in record:
                recognized = True
                values = record[key] if isinstance(record[key], list) else [record[key]]
                for value in values:
                    _add(buckets, cat, value, context)
    if recognized:
        return
    cat = record.get("category", category)
    if cat not in CATEGORIES:
        raise ValueError(f"{context}: missing or invalid category")
    if "canonical" not in record and "name" not in record:
        raise ValueError(f"{context}: expected canonical or name")
    _add(buckets, cat, record.get("canonical", record.get("name")), context)


def _read_aliases(path: Path) -> dict[Category, dict[str, tuple[str, ...]]]:
    aliases: dict[Category, dict[str, tuple[str, ...]]] = {cat: {} for cat in CATEGORIES}
    if not path.is_file():
        return aliases
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: aliases must be an object")
    for cat, mapping in payload.items():
        if cat not in CATEGORIES or not isinstance(mapping, dict):
            raise ValueError(f"{path}: invalid alias category {cat!r}")
        for canonical, values in mapping.items():
            if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
                raise ValueError(f"{path}: aliases for {canonical!r} must be a list of strings")
            aliases[cat][canonical.strip()] = tuple(value.strip() for value in values if value.strip())
    return aliases


def load_database(database_dir: Path) -> tuple[dict[Category, list[str]], dict[Category, dict[str, tuple[str, ...]]]]:
    directory = Path(database_dir)
    if not directory.is_dir():
        raise FileNotFoundError(f"Database directory not found: {directory}")
    buckets: dict[Category, list[str]] = {cat: [] for cat in CATEGORIES}
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.name.lower() in ("aliases.json", "prefixes.json"):
            continue
        category = _file_category(path)
        suffix = path.suffix.lower()
        if suffix == ".txt" and category is not None:
            with path.open(encoding="utf-8-sig") as stream:
                for number, line in enumerate(stream, 1):
                    _add(buckets, category, line, f"{path}:{number}")
        elif suffix == ".csv":
            _read_csv(path, buckets)
        elif suffix == ".jsonl":
            with path.open(encoding="utf-8-sig") as stream:
                for number, line in enumerate(stream, 1):
                    if line.strip():
                        _read_record(json.loads(line), buckets, f"{path}:{number}", category)
        elif suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            records = payload if isinstance(payload, list) else [payload]
            for record in records:
                _read_record(record, buckets, str(path), category)
    if not any(buckets.values()):
        raise ValueError(f"No address dictionary entries found in: {directory}")
    return buckets, _read_aliases(directory / "aliases.json")
