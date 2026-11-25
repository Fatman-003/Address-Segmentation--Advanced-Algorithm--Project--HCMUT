from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Iterable, Mapping


@dataclass(slots=True)
class _BuilderNode:
    children: dict[str, _BuilderNode] = field(default_factory=dict)
    canonical: dict[str, None] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class _Node:
    children: Mapping[str, _Node]
    canonical: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WordTrie:
    _root: _Node

    @classmethod
    def from_pairs(cls, pairs: Iterable[tuple[str, str]]) -> WordTrie:
        root = _BuilderNode()
        for key, canonical in pairs:
            words = key.split()
            if not words:
                raise ValueError("Cannot insert an empty search key")
            node = root
            for word in words:
                child = node.children.get(word)
                if child is None:
                    child = _BuilderNode()
                    node.children[word] = child
                node = child
            node.canonical[canonical] = None

        frozen: dict[int, _Node] = {}
        stack = [(root, False)]
        while stack:
            node, visited = stack.pop()
            if not visited:
                stack.append((node, True))
                stack.extend((child, False) for child in node.children.values())
            else:
                frozen[id(node)] = _Node(
                    MappingProxyType({word: frozen[id(child)] for word, child in node.children.items()}),
                    tuple(node.canonical),
                )
        return cls(frozen[id(root)])

    def _walk(self, key: str) -> _Node | None:
        words = key.split()
        if not words:
            return None
        node = self._root
        for word in words:
            node = node.children.get(word)
            if node is None:
                return None
        return node

    def exact(self, key: str) -> list[str]:
        node = self._walk(key)
        return list(node.canonical) if node else []

    def prefix(self, key: str, limit: int = 10) -> list[str]:
        if limit <= 0:
            return []
        root = self._walk(key)
        if root is None:
            return []
        result: list[str] = []
        seen: set[str] = set()
        stack = [root]
        while stack:
            node = stack.pop()
            for canonical in node.canonical:
                if canonical not in seen:
                    seen.add(canonical)
                    result.append(canonical)
                    if len(result) == limit:
                        return result
            stack.extend(reversed(tuple(node.children.values())))
        return result
