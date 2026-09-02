"""Hybrid search: BM25 (Tantivy) + vector (FAISS) results merged with
Reciprocal Rank Fusion. Exposed through the same `search(query, k) ->
list[doc_id]` shape as every other index in this harness.
"""
from __future__ import annotations

from pathlib import Path

from eval.fusion import reciprocal_rank_fusion
from ingest.embeddings import embed_texts
from ingest.index_faiss import VectorIndex
from ingest.index_tantivy import BM25Index
from ingest.vector_registry import VectorRegistry


def _collapse_to_doc_ids(ordered_items) -> list[str]:
    seen: dict[str, None] = {}
    for doc_id in ordered_items:
        seen.setdefault(doc_id, None)
    return list(seen.keys())


class HybridIndex:
    def __init__(
        self,
        tantivy_dir: Path,
        faiss_path: Path,
        vector_registry_db: Path,
        chunk_fanout: int = 100,
        rrf_k: int = 60,
    ):
        self._bm25 = BM25Index(tantivy_dir)
        self._vector_index = VectorIndex(faiss_path)
        self._vector_registry = VectorRegistry(vector_registry_db)
        self._chunk_fanout = chunk_fanout
        self._rrf_k = rrf_k

    def _bm25_doc_ids(self, query: str, limit: int) -> list[str]:
        hits = self._bm25.search(query, limit=max(self._chunk_fanout, limit))
        return _collapse_to_doc_ids(h.doc_id for h in hits)

    def _vector_doc_ids(self, query: str, limit: int) -> list[str]:
        query_vector = embed_texts([query])[0]
        fanout = max(self._chunk_fanout, limit)
        scores, ids = self._vector_index.search(query_vector, fanout)
        valid_ids = [int(i) for i in ids if i != -1]
        records = self._vector_registry.get_active_by_ids(valid_ids)
        # ids come back from FAISS already sorted by descending score
        ordered_doc_ids = (records[i].doc_id for i in valid_ids if i in records)
        return _collapse_to_doc_ids(ordered_doc_ids)

    def search(self, query: str, k: int) -> list[str]:
        bm25_ranking = self._bm25_doc_ids(query, k)
        vector_ranking = self._vector_doc_ids(query, k)
        fused = reciprocal_rank_fusion([bm25_ranking, vector_ranking], k=self._rrf_k)
        return fused[:k]
