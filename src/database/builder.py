from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Iterator, Mapping

from .loader import load_database
from .normalizer import CATEGORIES, Category, normalize_key, strip_prefix
from .trie import WordTrie


@dataclass(frozen=True, slots=True)
class DatabaseEntry:
    canonical: str
    category: Category
    normalized: str


def _keys(text: str, category: Category) -> tuple[str, ...]:
    full = normalize_key(text)
    stripped = strip_prefix(full, category)
    variants = (full, stripped, full.replace(" ", ""), stripped.replace(" ", ""))
    return tuple(dict.fromkeys(key for key in variants if key))


def _index_pairs(
    entries: tuple[DatabaseEntry, ...], aliases: Mapping[str, tuple[str, ...]], category: Category
) -> Iterator[tuple[str, str]]:
    for entry in entries:
        for key in _keys(entry.canonical, category):
            yield key, entry.canonical
        for alias in aliases.get(entry.canonical, ()):
            full = normalize_key(alias)
            for key in dict.fromkeys((full, full.replace(" ", ""))):
                if key:
                    yield key, entry.canonical


@dataclass(frozen=True, slots=True)
class AddressIndex:
    tries: Mapping[Category, WordTrie]
    _entries: Mapping[Category, tuple[DatabaseEntry, ...]]
    _canonical_sets: Mapping[Category, frozenset[str]]
    aliases: Mapping[Category, Mapping[str, tuple[str, ...]]]

    def _trie(self, field: str) -> WordTrie:
        if field not in self.tries:
            raise ValueError(f"Invalid field {field!r}; expected one of {CATEGORIES}")
        return self.tries[field]

    def exact_lookup(self, field: Category, text: str) -> list[str]:
        trie = self._trie(field)
        candidates = (canonical for key in _keys(text, field) for canonical in trie.exact(key))
        return list(dict.fromkeys(candidates))

    def prefix_lookup(self, field: Category, text: str, limit: int = 10) -> list[str]:
        trie = self._trie(field)
        return trie.prefix(normalize_key(text), limit)

    def entries(self, category: Category | None = None) -> tuple[DatabaseEntry, ...]:
        if category is not None:
            self._trie(category)
            return self._entries[category]
        return tuple(entry for cat in CATEGORIES for entry in self._entries[cat])

    def contains_canonical(self, value: str, category: Category | None = None) -> bool:
        if category is not None:
            self._trie(category)
            return value in self._canonical_sets[category]
        return any(value in self._canonical_sets[cat] for cat in CATEGORIES)

    def stats(self) -> dict[str, object]:
        counts = {cat: len(self._entries[cat]) for cat in CATEGORIES}
        return {"counts": counts, "total_entries": sum(counts.values())}


def build_index(database_dir: Path) -> AddressIndex:
    buckets, raw_aliases = load_database(database_dir)
    entries = {
        cat: tuple(
            DatabaseEntry(name, cat, strip_prefix(normalize_key(name), cat))
            for name in dict.fromkeys(buckets[cat])
        )
        for cat in CATEGORIES
    }
    canonical_sets = {cat: frozenset(entry.canonical for entry in entries[cat]) for cat in CATEGORIES}
    aliases = {
        cat: MappingProxyType({
            name: values for name, values in raw_aliases[cat].items() if name in canonical_sets[cat]
        })
        for cat in CATEGORIES
    }
    tries = {
        cat: WordTrie.from_pairs(_index_pairs(entries[cat], aliases[cat], cat))
        for cat in CATEGORIES
    }
    return AddressIndex(
        MappingProxyType(tries), MappingProxyType(entries), MappingProxyType(canonical_sets), MappingProxyType(aliases)
    )
