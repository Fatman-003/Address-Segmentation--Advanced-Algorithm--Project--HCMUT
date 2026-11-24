"""Simple address dictionary with Vietnamese normalization and edit-distance matching.

Supports exact/alias lookup and highest-similarity matching using Levenshtein
Edit Distance with a configurable acceptance threshold.
"""
from __future__ import annotations

from collections import defaultdict
import csv
from dataclasses import dataclass
import json
from pathlib import Path
import re
import unicodedata
from typing import Iterable, Literal, Mapping, Sequence

Category = Literal["street", "ward", "province"]
CATEGORIES: tuple[Category, ...] = ("street", "ward", "province")

_D_STROKE_MAP = str.maketrans({"đ": "d", "Đ": "D"})
_NON_ALNUM_RE = re.compile(r"[^\w\s/]", flags=re.UNICODE)
_SLASH_SPACE_RE = re.compile(r"\s*/\s*")
_WHITESPACE_RE = re.compile(r"\s+")
_GLUED_PREFIX_RE = re.compile(r"^(p|ph|x|tt|dk|d|ql|tl|xl|hl)(\d+[a-z]?(?:/\d+[a-z]?)?)$")
_ALLEY_PREFIX_RE = re.compile(
    r"^(?:ngach|hem|ngo|kiet|hom)\s+(?:so\s+\d+(?:/\d+)*[a-z]?|\d+(?:/\d+)*[a-z]?|[a-z](?=\s+\S+\s+\S+))\s+"
)

_DEFAULT_STRIP_PREFIXES: dict[Category, tuple[str, ...]] = {
    "province": ("thanh pho truc thuoc trung uong", "thanh pho", "tinh", "tp", "t"),
    "ward": ("phuong", "dac khu", "thi tran", "xa", "ph", "dk", "tt", "p", "x"),
    "street": ("duong", "pho", "d"),
}

_GLUED_EXPANSIONS: dict[Category, dict[str, str]] = {
    "province": {},
    "ward": {"p": "phuong", "ph": "phuong", "x": "xa", "tt": "thi tran", "dk": "dac khu"},
    "street": {"d": "duong", "ql": "quoc lo", "tl": "tinh lo", "xl": "xa lo", "hl": "huong lo"},
}


@dataclass(frozen=True, slots=True)
class DictionaryEntry:
    """One canonical entry loaded from the reference database."""

    canonical: str
    category: Category
    normalized: str


@dataclass(frozen=True, slots=True)
class MatchResult:
    """Matched canonical entry along with similarity score in [0.0, 1.0]."""

    canonical: str
    category: Category
    score: float
    method: str


def remove_vietnamese_diacritics(text: str) -> str:
    """Fold Vietnamese diacritics to ASCII base characters."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFD", text.translate(_D_STROKE_MAP))
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def normalize_text(text: str) -> str:
    """Lowercase, fold diacritics, clean punctuation, and keep slashes (e.g. ``3/2``)."""
    if not text:
        return ""
    folded = remove_vietnamese_diacritics(text).lower().replace("_", " ")
    cleaned = _NON_ALNUM_RE.sub(" ", folded)
    cleaned = _SLASH_SPACE_RE.sub("/", cleaned)
    return _WHITESPACE_RE.sub(" ", cleaned).strip()


def strip_prefix(normalized_text: str, category: Category) -> str:
    """Remove administrative or alley prefixes and expand glued shortcuts (e.g. ``p1``, ``ql1a``)."""
    if not normalized_text:
        return ""

    text = normalized_text
    tokens = text.split()
    if tokens:
        if category == "province" and len(tokens) >= 2 and tokens[0] == "t" and tokens[1] == "p":
            text = " ".join(["thanh", "pho", *tokens[2:]])
        else:
            glued = _GLUED_PREFIX_RE.match(tokens[0])
            if glued:
                prefix_tok, rest = glued.groups()
                expanded = _GLUED_EXPANSIONS[category].get(prefix_tok, prefix_tok)
                text = " ".join([*expanded.split(), rest, *tokens[1:]])

    if category == "street":
        stripped_alley = _ALLEY_PREFIX_RE.sub("", text, count=1).strip()
        if stripped_alley:
            text = stripped_alley

    for prefix in _DEFAULT_STRIP_PREFIXES[category]:
        marker = f"{prefix} "
        if text.startswith(marker):
            rest = text[len(marker) :].strip()
            if rest:
                return rest
    return text


def edit_distance(a: str, b: str) -> int:
    """Compute Levenshtein edit distance between two normalized strings."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    if len(a) < len(b):
        a, b = b, a

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


def edit_similarity(a: str, b: str) -> float:
    """Normalized Levenshtein similarity in [0.0, 1.0]."""
    if a == b:
        return 1.0 if a else 0.0
    if not a or not b:
        return 0.0
    return 1.0 - edit_distance(a, b) / max(len(a), len(b))


def _read_txt(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def _read_csv_columns(path: Path, buckets: dict[Category, list[str]]) -> None:
    text = path.read_text(encoding="utf-8-sig")
    for row in csv.DictReader(text.splitlines()):
        for key, val in row.items():
            if not key or not val:
                continue
            norm_key = normalize_text(key)
            for cat in CATEGORIES:
                if norm_key in (cat, f"{cat}s") and val.strip():
                    buckets[cat].append(val.strip())


def _read_aliases(path: Path) -> dict[Category, dict[str, list[str]]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    aliases: dict[Category, dict[str, list[str]]] = {cat: {} for cat in CATEGORIES}
    if not isinstance(payload, Mapping):
        return aliases
    for cat in CATEGORIES:
        raw_map = payload.get(cat)
        if not isinstance(raw_map, Mapping):
            continue
        for canonical, alias_list in raw_map.items():
            if isinstance(alias_list, Sequence) and not isinstance(alias_list, (str, bytes)):
                aliases[cat][str(canonical).strip()] = [str(a).strip() for a in alias_list if str(a).strip()]
    return aliases


class AddressDictionary:
    """Address dictionary supporting exact lookup and highest-similarity matching."""

    def __init__(
        self,
        entries_by_category: Mapping[Category, Sequence[DictionaryEntry]],
        aliases: Mapping[Category, Mapping[str, Sequence[str]]] | None = None,
    ) -> None:
        self._entries: dict[Category, tuple[DictionaryEntry, ...]] = {
            cat: tuple(entries_by_category.get(cat, ())) for cat in CATEGORIES
        }
        self._canonical_sets: dict[Category, frozenset[str]] = {
            cat: frozenset(e.canonical for e in self._entries[cat]) for cat in CATEGORIES
        }
        self._exact_map: dict[Category, dict[str, tuple[DictionaryEntry, ...]]] = {}
        self._alias_keys_count: dict[Category, int] = {}
        self._build_exact_index(aliases or {})

    def _build_exact_index(self, aliases: Mapping[Category, Mapping[str, Sequence[str]]]) -> None:
        for cat in CATEGORIES:
            buckets: dict[str, list[DictionaryEntry]] = defaultdict(list)
            by_canonical = {e.canonical: e for e in self._entries[cat]}

            for entry in self._entries[cat]:
                norm_full = normalize_text(entry.canonical)
                for key in (norm_full, entry.normalized, norm_full.replace(" ", ""), entry.normalized.replace(" ", "")):
                    if key:
                        buckets[key].append(entry)

            alias_count = 0
            for canonical, alias_list in aliases.get(cat, {}).items():
                entry = by_canonical.get(canonical)
                if entry is None:
                    continue
                for raw_alias in alias_list:
                    norm_alias = normalize_text(raw_alias)
                    if not norm_alias:
                        continue
                    alias_count += 1
                    buckets[norm_alias].append(entry)
                    compact_alias = norm_alias.replace(" ", "")
                    if compact_alias != norm_alias:
                        buckets[compact_alias].append(entry)

            self._alias_keys_count[cat] = alias_count
            self._exact_map[cat] = {k: tuple(dict.fromkeys(v)) for k, v in buckets.items()}

    @classmethod
    def from_lists(
        cls,
        *,
        streets: Iterable[str] = (),
        wards: Iterable[str] = (),
        provinces: Iterable[str] = (),
        aliases: Mapping[Category, Mapping[str, Sequence[str]]] | None = None,
    ) -> AddressDictionary:
        """Build a dictionary from in-memory lists of canonical strings."""
        raw_lists: dict[Category, Iterable[str]] = {
            "street": streets,
            "ward": wards,
            "province": provinces,
        }
        entries_by_cat: dict[Category, list[DictionaryEntry]] = {}
        for cat in CATEGORIES:
            seen: set[str] = set()
            items: list[DictionaryEntry] = []
            for raw in raw_lists[cat]:
                canonical = raw.strip()
                if not canonical or canonical in seen:
                    continue
                seen.add(canonical)
                norm = strip_prefix(normalize_text(canonical), cat)
                items.append(DictionaryEntry(canonical=canonical, category=cat, normalized=norm))
            entries_by_cat[cat] = items
        return cls(entries_by_category=entries_by_cat, aliases=aliases)

    @classmethod
    def from_directory(cls, database_dir: Path) -> AddressDictionary:
        """Load dictionary files (``.txt``, ``.csv``, ``aliases.json``) from ``database_dir``."""
        db_path = Path(database_dir)
        if not db_path.is_dir():
            raise FileNotFoundError(f"Database directory not found: {db_path}")

        buckets: dict[Category, list[str]] = {cat: [] for cat in CATEGORIES}
        file_stems = {
            "street": ("street", "streets", "duong"),
            "ward": ("ward", "wards", "phuong", "xa"),
            "province": ("province", "provinces", "tinh"),
        }

        for path in sorted(db_path.iterdir()):
            if not path.is_file():
                continue
            stem = normalize_text(path.stem)
            suffix = path.suffix.lower()
            if suffix == ".txt":
                for cat, names in file_stems.items():
                    if stem in names:
                        buckets[cat].extend(_read_txt(path))
            elif suffix == ".csv":
                _read_csv_columns(path, buckets)
            elif suffix == ".jsonl" and path.name != "aliases.json":
                for line in _read_txt(path):
                    obj = json.loads(line)
                    if isinstance(obj, Mapping):
                        cat = str(obj.get("category", "")).strip().lower()
                        name = str(obj.get("name", obj.get("canonical", ""))).strip()
                        if cat in CATEGORIES and name:
                            buckets[cat].append(name)  # type: ignore[index]

        if not any(buckets.values()):
            raise ValueError(f"No address dictionary entries found in: {db_path}")

        aliases_path = db_path / "aliases.json"
        aliases = _read_aliases(aliases_path) if aliases_path.is_file() else None
        return cls.from_lists(
            streets=buckets["street"],
            wards=buckets["ward"],
            provinces=buckets["province"],
            aliases=aliases,
        )

    def entries(self, category: Category | None = None) -> tuple[DictionaryEntry, ...]:
        """Return canonical entries for one category or all three categories."""
        if category is not None:
            return self._entries[category]
        return (*self._entries["street"], *self._entries["ward"], *self._entries["province"])

    def contains_canonical(self, value: str, category: Category | None = None) -> bool:
        """Check whether ``value`` is an exact canonical entry in the loaded DB."""
        if category is not None:
            return value in self._canonical_sets[category]
        return any(value in self._canonical_sets[cat] for cat in CATEGORIES)

    def lookup_exact(self, query: str, category: Category | None = None) -> list[MatchResult]:
        """Return all exact/prefix-stripped/alias/compact matches (score = 1.0)."""
        norm = normalize_text(query)
        if not norm:
            return []

        cats = (category,) if category is not None else CATEGORIES
        results: list[MatchResult] = []
        seen: set[tuple[Category, str]] = set()

        for cat in cats:
            stripped = strip_prefix(norm, cat)
            keys = (norm, stripped, norm.replace(" ", ""), stripped.replace(" ", ""))
            for key in dict.fromkeys(keys):
                for entry in self._exact_map[cat].get(key, ()):
                    pair = (entry.category, entry.canonical)
                    if pair not in seen:
                        seen.add(pair)
                        results.append(
                            MatchResult(
                                canonical=entry.canonical,
                                category=entry.category,
                                score=1.0,
                                method="exact",
                            )
                        )
        return results

    def search(
        self,
        query: str,
        category: Category,
        *,
        top_k: int = 5,
        threshold: float = 0.0,
    ) -> list[MatchResult]:
        """Rank entries in ``category`` by edit similarity and return top ``k`` >= ``threshold``."""
        exact = self.lookup_exact(query, category=category)
        if exact:
            return exact[:top_k]

        query_key = strip_prefix(normalize_text(query), category)
        if not query_key:
            return []

        scored: list[MatchResult] = []
        q_len = len(query_key)
        best_score = threshold

        for entry in self._entries[category]:
            if entry.normalized:
                max_len = max(q_len, len(entry.normalized))
                min_needed = best_score if top_k == 1 else threshold
                if min_needed > 0.0 and 1.0 - abs(q_len - len(entry.normalized)) / max_len < min_needed:
                    continue
            score = edit_similarity(query_key, entry.normalized)
            if score >= threshold:
                if top_k == 1 and score > best_score:
                    best_score = score
                scored.append(
                    MatchResult(
                        canonical=entry.canonical,
                        category=category,
                        score=round(score, 6),
                        method="edit",
                    )
                )

        scored.sort(key=lambda item: (-item.score, item.canonical))
        return scored[:top_k]

    def find_best(
        self,
        query: str,
        category: Category,
        *,
        threshold: float = 0.6,
    ) -> MatchResult | None:
        """Return the single entry with the highest edit similarity >= ``threshold``, else ``None``."""
        matches = self.search(query, category, top_k=1, threshold=threshold)
        return matches[0] if matches else None

    def stats(self) -> dict[str, object]:
        """Return counts of canonical entries and registered aliases per category."""
        counts = {cat: len(self._entries[cat]) for cat in CATEGORIES}
        return {
            "counts": counts,
            "total_entries": sum(counts.values()),
            "aliases": dict(self._alias_keys_count),
        }
