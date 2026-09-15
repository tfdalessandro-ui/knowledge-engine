"""Hybrid search: BM25 (Tantivy) + vector (FAISS) results merged either by
Reciprocal Rank Fusion (rank-only, scale-agnostic) or weighted score fusion
(`eval.weighted_fusion`, min-max normalized raw scores -- keeps magnitude
information RRF discards). `search()` exposes the same
`search(query, k) -> list[doc_id]` shape as every other index in this
harness (used by eval.run). `search_detailed()` additionally returns each
candidate's BM25 score, vector score, and fused score, chunk-level -- P3's
query-log capture needs these as future LTR features, not just the final
fused doc_id order.

Restored 2026-09-15: fusion_mode="weighted"/alpha=0.535 were tuned via two
rounds of cross-validated GA search (LOGBOOK_09042026_060353.md) and found
to beat RRF, but the settings were never actually threaded through to this
class -- api/main.py's `_get_index()` built HybridIndex() with no kwargs
at all, so the live service always ran plain RRF with rrf_k defaulted to
60 (not the tuned rrf_k=1) regardless of Settings. Root-caused after a
concrete symptom: an exact part-code match sometimes ranked below a
document that was merely decent on both BM25 and vector sides, because
RRF gives identical credit to "barely rank 1" and "overwhelmingly rank 1"
-- exactly the failure mode weighted fusion's magnitude-preserving design
exists to avoid. `src/eval/weighted_fusion.py` itself was recovered from
an uncommitted copy that had been silently dropped by an unrelated
repo/execution-split migration the same week; see that file's own
docstring and TODO.md for the full story.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from eval.fusion import reciprocal_rank_fusion, rrf_scores
from eval.weighted_fusion import weighted_fusion_scores
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
        fusion_mode: str = "rrf",
        alpha: float = 0.5,
    ):
        if fusion_mode not in ("rrf", "weighted"):
            raise ValueError(f"fusion_mode must be 'rrf' or 'weighted', got {fusion_mode!r}")
        self._bm25 = BM25Index(tantivy_dir)
        self._vector_index = VectorIndex(faiss_path)
        self._vector_registry = VectorRegistry(vector_registry_db)
        self._chunk_fanout = chunk_fanout
        self._rrf_k = rrf_k
        self._fusion_mode = fusion_mode
        self._alpha = alpha

    def _bm25_hits(self, query: str, limit: int):
        return self._bm25.search(query, limit=max(self._chunk_fanout, limit))

    def _bm25_best_scores(self, query: str, limit: int) -> tuple[list[str], dict[str, tuple[float, str, str]]]:
        """Best (highest-scoring) chunk per doc_id, in Tantivy's own
        descending-score order -- needed for weighted fusion's raw scores,
        not just the rank-ordered doc_id list RRF uses."""
        ranking: list[str] = []
        best: dict[str, tuple[float, str, str]] = {}
        for h in self._bm25_hits(query, limit):
            if h.doc_id not in best:
                ranking.append(h.doc_id)
                best[h.doc_id] = (h.score, h.chunk_id, h.text)
        return ranking, best

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
        if self._fusion_mode == "weighted":
            return [d for d, _ in self._weighted_fused(query, k)][:k]
        bm25_ranking = _collapse_to_doc_ids(h.doc_id for h in self._bm25_hits(query, k))
        vector_ranking, _ = self._vector_hits(query, k)
        fused = reciprocal_rank_fusion([bm25_ranking, vector_ranking], k=self._rrf_k)
        return fused[:k]

    def _weighted_fused(self, query: str, k: int):
        """Returns [(doc_id, fused_score), ...] sorted descending, plus
        (as a side channel via instance state read by search_detailed)
        the raw per-side score/chunk/text maps."""
        _, bm25_best = self._bm25_best_scores(query, k)
        _, vector_best = self._vector_hits(query, k)
        bm25_scores = {d: s for d, (s, _, _) in bm25_best.items()}
        vector_scores = {d: s for d, (s, _, _) in vector_best.items()}
        fused_scores = weighted_fusion_scores(bm25_scores, vector_scores, alpha=self._alpha)
        self._last_bm25_best = bm25_best
        self._last_vector_best = vector_best
        return sorted(fused_scores.items(), key=lambda kv: -kv[1])

    def search_detailed(self, query: str, k: int) -> list[DetailedHit]:
        if self._fusion_mode == "weighted":
            fused = self._weighted_fused(query, k)[:k]
            bm25_best = self._last_bm25_best
            vector_best = self._last_vector_best
            results = []
            for rank, (doc_id, score) in enumerate(fused):
                bm25_score, bm25_chunk, bm25_text = bm25_best.get(doc_id, (None, None, None))
                vector_score, vector_chunk, vector_text = vector_best.get(doc_id, (None, None, None))
                results.append(
                    DetailedHit(
                        doc_id=doc_id,
                        chunk_id=bm25_chunk or vector_chunk,
                        rank=rank,
                        bm25_score=bm25_score,
                        vector_score=vector_score,
                        rrf_score=score,
                        text=bm25_text or vector_text,
                    )
                )
            return results

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
