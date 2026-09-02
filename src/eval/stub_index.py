"""A dummy search index used ONLY to prove the eval harness computes metrics
correctly. No real retrieval logic lives here — that's P1 (BM25 indexing).

The stub is deliberately deterministic and judgment-aware in a controlled way,
so a known-answer test can assert exact metric values against it.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol


class SearchIndex(Protocol):
    def search(self, query: str, k: int) -> list[str]:
        ...


class PerfectStubIndex:
    """Returns judged-relevant docs first (best relevance first), then padding.

    Used to sanity-check the harness against a known-optimal ranking (expected
    nDCG@10 == 1.0 for any query with judgments).
    """

    def __init__(self, judgments_by_query: dict[str, dict[str, int]], all_doc_ids: list[str]):
        self._judgments_by_query = judgments_by_query
        self._all_doc_ids = all_doc_ids

    def search(self, query: str, k: int) -> list[str]:
        judgments = self._judgments_by_query.get(query, {})
        ranked = sorted(judgments, key=lambda d: judgments[d], reverse=True)
        padding = [d for d in self._all_doc_ids if d not in judgments]
        return (ranked + padding)[:k]


class ShuffledStubIndex:
    """Returns docs in a fixed, query-agnostic order (ignores relevance).

    Used to sanity-check the harness catches a *bad* ranking (expected
    metrics strictly below the perfect index's, above zero).
    """

    def __init__(self, all_doc_ids: list[str]):
        self._all_doc_ids = all_doc_ids

    def search(self, query: str, k: int) -> list[str]:
        return self._all_doc_ids[:k]


class NullStubIndex:
    """Always returns nothing relevant (deterministic worst case, all-zero doc_ids)."""

    def __init__(self, all_doc_ids: list[str]):
        self._decoy_ids = [f"__decoy_{i}__" for i in range(len(all_doc_ids))]

    def search(self, query: str, k: int) -> list[str]:
        return self._decoy_ids[:k]


def load_judgments(path: Path) -> dict[str, dict[str, int]]:
    """judgments.json -> {query: {doc_id: relevance}}"""
    raw = json.loads(path.read_text(encoding="utf-8"))
    by_query: dict[str, dict[str, int]] = {}
    for row in raw:
        by_query.setdefault(row["query"], {})[row["doc_id"]] = int(row["relevance"])
    return by_query
