"""Adapter: the real Tantivy BM25 index, exposed through the same
`search(query, k) -> list[doc_id]` shape the eval harness's stub indices use,
so `eval.run --index real` scores it with the identical metric code.

A query can retrieve several chunks from the same document; this collapses
those to one doc_id entry at its best (first/highest-scoring) rank, since the
P0 judgment set grades relevance at the document level, not the chunk level.
"""
from __future__ import annotations

from pathlib import Path

from ingest.index_tantivy import BM25Index


class RealBM25Index:
    def __init__(self, index_dir: Path, chunk_fanout: int = 100):
        self._index = BM25Index(index_dir)
        self._chunk_fanout = chunk_fanout  # chunks to pull before collapsing to doc_ids

    def search(self, query: str, k: int) -> list[str]:
        hits = self._index.search(query, limit=max(self._chunk_fanout, k))
        seen: dict[str, None] = {}
        for hit in hits:
            seen.setdefault(hit.doc_id, None)
        return list(seen.keys())[:k]
