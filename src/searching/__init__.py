"""Searching package: address dictionary and edit-distance similarity matching."""

from src.searching.dictionary import (
    CATEGORIES,
    AddressDictionary,
    DictionaryEntry,
    MatchResult,
    edit_distance,
    edit_similarity,
    normalize_text,
    remove_vietnamese_diacritics,
    strip_prefix,
)

__all__ = [
    "CATEGORIES",
    "AddressDictionary",
    "DictionaryEntry",
    "MatchResult",
    "edit_distance",
    "edit_similarity",
    "normalize_text",
    "remove_vietnamese_diacritics",
    "strip_prefix",
]
