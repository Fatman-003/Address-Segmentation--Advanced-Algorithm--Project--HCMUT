from __future__ import annotations

import re
import unicodedata
from typing import Literal


Category = Literal["street", "ward", "province"]
CATEGORIES: tuple[Category, ...] = ("street", "ward", "province")

_D_STROKE_MAP = str.maketrans({"đ": "d", "Đ": "D"})
_NON_ALNUM_RE = re.compile(r"[^\w\s/]", flags=re.UNICODE)
_SLASH_SPACE_RE = re.compile(r"\s*/\s*")
_WHITESPACE_RE = re.compile(r"\s+")
_GLUED_PREFIX_RE = re.compile(r"^(p|ph|x|tt|dk|d|ql|tl|xl|hl)(\d+[a-z]?(?:/\d+[a-z]?)?)$")
_ALLEY_PREFIX_RE = re.compile(
    r"^(?:ngach|hem|ngo|kiet|hom)\s+"
    r"(?:so\s+\d+(?:/\d+)*[a-z]?|\d+(?:/\d+)*[a-z]?|[a-z](?=\s+\S+\s+\S+))\s+"
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

def remove_vietnamese_diacritics(text: str) -> str:
    if not text:
        return ''
    decomposed = unicodedata.normalize('NFD', text.translate(_D_STROKE_MAP))
    return ''.join(ch for ch in decomposed if unicodedata.category(ch) != 'Mn')

def normalize_text(text: str) -> str:
    if not text:
        return ''
    folded = remove_vietnamese_diacritics(text).lower().replace('_', ' ')
    cleaned = _NON_ALNUM_RE.sub(' ', folded)
    cleaned = _SLASH_SPACE_RE.sub('/', cleaned)
    return _WHITESPACE_RE.sub(' ', cleaned).strip()

def strip_prefix(normalized_text: str, category: Category) -> str:
    if not normalized_text:
        return ''
    text = normalized_text
    tokens = text.split()
    if tokens:
        if category == 'province' and len(tokens) >= 2 and tokens[0] == 't' and tokens[1] == 'p':
            text = ' '.join(['thanh', 'pho', *tokens[2:]])
        else:
            glued = _GLUED_PREFIX_RE.match(tokens[0])
            if glued:
                prefix_tok, rest = glued.groups()
                expanded = _GLUED_EXPANSIONS[category].get(prefix_tok, prefix_tok)
                text = ' '.join([*expanded.split(), rest, *tokens[1:]])
    if category == 'street':
        stripped_alley = _ALLEY_PREFIX_RE.sub('', text, count=1).strip()
        if stripped_alley:
            text = stripped_alley
    for prefix in _DEFAULT_STRIP_PREFIXES[category]:
        marker = f'{prefix} '
        if text.startswith(marker):
            rest = text[len(marker):].strip()
            if rest:
                return rest
    return text

def normalize_key(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("normalize_key expects str")
    return normalize_text(text)
