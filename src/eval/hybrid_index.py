"""Hybrid search: BM25 (Tantivy) + vector (FAISS) results merged with
Reciprocal Rank Fusion. `search()` exposes the same `search(query, k) ->
list[doc_id]` shape as every other index in this harness (used by eval.run).
`search_detailed()` additionally returns each candidate's BM25 score, vector
score, and RRF score, chunk-level -- P3's query-log capture needs these as
future LTR features, not just the final fused doc_id order.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from eval.fusion import reciprocal_rank_fusion, rrf_scores
from ingest.embeddings import embed_texts
from ingest.index_faiss import VectorIndex
from ingest.index_tantivy import BM25Index
from ingest.vector_registry import VectorRegistry


@dataclass
class DetailedHit:
    doc_id: str
    chunk_id: str | None
    rank: int
    bm25_score: float | None
    vector_score: float | None
    rrf_score: float
    text: str | None = None


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

    def _bm25_hits(self, query: str, limit: int):
        return self._bm25.search(query, limit=max(self._chunk_fanout, limit))

    def _vector_hits(self, query: str, limit: int):
        """Returns (ordered_doc_ids, {doc_id: (score, chunk_id, text)}) --
        best hit per doc (first occurrence, since FAISS already sorts by
        descending score)."""
        query_vector = embed_texts([query])[0]
        fanout = max(self._chunk_fanout, limit)
        scores, ids = self._vector_index.search(query_vector, fanout)
        valid_ids = [int(i) for i in ids if i != -1]
        records = self._vector_registry.get_active_by_ids(valid_ids)
        score_by_id = dict(zip((int(i) for i in ids), scores))

        ordered_doc_ids: list[str] = []
        best_by_doc: dict[str, tuple[float, str, str]] = {}
        for vid in valid_ids:
            record = records.get(vid)
            if record is None:
                continue
            if record.doc_id not in best_by_doc:
                ordered_doc_ids.append(record.doc_id)
                best_by_doc[record.doc_id] = (float(score_by_id[vid]), record.chunk_id, record.text)
        return ordered_doc_ids, best_by_doc

    def search(self, query: str, k: int) -> list[str]:
        bm25_ranking = _collapse_to_doc_ids(h.doc_id for h in self._bm25_hits(query, k))
        vector_ranking, _ = self._vector_hits(query, k)
        fused = reciprocal_rank_fusion([bm25_ranking, vector_ranking], k=self._rrf_k)
        return fused[:k]

    def search_detailed(self, query: str, k: int) -> list[DetailedHit]:
        bm25_hits = self._bm25_hits(query, k)
        bm25_best: dict[str, tuple[float, str, str]] = {}
        bm25_ranking: list[str] = []
        for h in bm25_hits:
            if h.doc_id not in bm25_best:
                bm25_ranking.append(h.doc_id)
                bm25_best[h.doc_id] = (h.score, h.chunk_id, h.text)

        vector_ranking, vector_best = self._vector_hits(query, k)

        scores, _ = rrf_scores([bm25_ranking, vector_ranking], k=self._rrf_k)
        fused_doc_ids = sorted(scores, key=lambda d: -scores[d])[:k]

        results = []
        for rank, doc_id in enumerate(fused_doc_ids):
            bm25_score, bm25_chunk, bm25_text = bm25_best.get(doc_id, (None, None, None))
            vector_score, vector_chunk, vector_text = vector_best.get(doc_id, (None, None, None))
            results.append(
                DetailedHit(
                    doc_id=doc_id,
                    chunk_id=bm25_chunk or vector_chunk,
                    rank=rank,
                    bm25_score=bm25_score,
                    vector_score=vector_score,
                    rrf_score=scores[doc_id],
                    text=bm25_text or vector_text,
                )
            )
        return results
