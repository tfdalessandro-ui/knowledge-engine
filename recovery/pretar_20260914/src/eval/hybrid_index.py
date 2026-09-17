"""Hybrid search: BM25 (Tantivy) + vector (FAISS) results merged with one
of two fusion strategies -- Reciprocal Rank Fusion (rank-only, the
original P2 mechanism) or weighted score fusion (`weighted_fusion.py`,
combines normalized raw scores directly). `search()` exposes the same
`search(query, k) -> list[doc_id]` shape as every other index in this
harness (used by eval.run). `search_detailed()` additionally returns each
candidate's BM25 score, vector score, and fused score, chunk-level -- P3's
query-log capture needs these as future LTR features, not just the final
fused doc_id order.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from eval.adaptive_alpha import adaptive_alpha
from eval.fusion import rrf_scores
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
    rrf_score: float  # kept as the field name for API/query-log backward
    # compatibility -- holds the fused score regardless of fusion_mode
    # (RRF's own score when fusion_mode="rrf", weighted_fusion's combined
    # score when fusion_mode="weighted"). Renaming this field would be a
    # breaking change to the /search response shape and query_log.db's
    # existing rows; not done here.
    text: str | None = None


class HybridIndex:
    def __init__(
        self,
        tantivy_dir: Path,
        faiss_path: Path,
        vector_registry_db: Path,
        # Defaults changed 2026-09-04, twice, both times after cross-
        # validated GA searches (see LOGBOOK_09042026_*.md for the full
        # investigation -- multiple attempts along the way that did NOT
        # hold up and were correctly never deployed, notably a round-1 CV
        # with too few held-out queries/fold that looked promising but was
        # confirmed to overfit).
        # (1) chunk_fanout=100,rrf_k=60 -> chunk_fanout=62,rrf_k=1 (RRF,
        #     stable across all 5 folds, +0.53% held-out avg).
        # (2) fusion_mode="rrf" -> "weighted" with alpha=0.535 -- a 5-fold
        #     CV directly comparing weighted score fusion against the
        #     just-deployed RRF config found weighted fusion ahead in 4/5
        #     folds (+1.44 to +1.94% held-out avg across two fanout-ceiling
        #     widths, vs RRF's +0.56%), with alpha converging tightly
        #     (0.535-0.548 in 4/5 folds at BOTH ceilings tested) -- alpha
        #     is the real, stable lever; chunk_fanout was noisy and not
        #     deployed at any single "true optimum" value, just a
        #     reasonable mid-range pick (100) since a wide range performed
        #     similarly.
        chunk_fanout: int = 100,
        rrf_k: int = 1,
        fusion_mode: str = "weighted",
        alpha: float = 0.535,
        # Adaptive alpha (fork point #3, LOGBOOK_09042026_060353.md):
        # when alpha_mode="adaptive", alpha is computed per query from
        # eval.adaptive_alpha instead of using the fixed `alpha` above --
        # see that module's own docstring for the model (deliberately a
        # simple 2-parameter linear function of query word count, to
        # avoid overfitting a small judgment set). `alpha` above is
        # ignored when alpha_mode="adaptive"; alpha_base/alpha_slope are
        # ignored when alpha_mode="fixed".
        alpha_mode: str = "fixed",
        alpha_base: float = 0.535,
        alpha_slope: float = 0.0,
    ):
        if fusion_mode not in ("rrf", "weighted"):
            raise ValueError(f"fusion_mode must be 'rrf' or 'weighted', got {fusion_mode!r}")
        if alpha_mode not in ("fixed", "adaptive"):
            raise ValueError(f"alpha_mode must be 'fixed' or 'adaptive', got {alpha_mode!r}")
        self._bm25 = BM25Index(tantivy_dir)
        self._vector_index = VectorIndex(faiss_path)
        self._vector_registry = VectorRegistry(vector_registry_db)
        self._chunk_fanout = chunk_fanout
        self._rrf_k = rrf_k
        self._fusion_mode = fusion_mode
        self._alpha = alpha
        self._alpha_mode = alpha_mode
        self._alpha_base = alpha_base
        self._alpha_slope = alpha_slope

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

    def _fuse(self, query: str, bm25_ranking: list[str], bm25_scores: dict[str, float], vector_ranking: list[str], vector_scores: dict[str, float]) -> dict[str, float]:
        """Returns fused score per doc_id, per self._fusion_mode."""
        if self._fusion_mode == "weighted":
            if self._alpha_mode == "adaptive":
                alpha = adaptive_alpha(query, self._alpha_base, self._alpha_slope)
            else:
                alpha = self._alpha
            return weighted_fusion_scores(bm25_scores, vector_scores, alpha=alpha)
        scores, _ = rrf_scores([bm25_ranking, vector_ranking], k=self._rrf_k)
        return scores

    def search(self, query: str, k: int) -> list[str]:
        return [hit.doc_id for hit in self.search_detailed(query, k)]

    def search_detailed(self, query: str, k: int) -> list[DetailedHit]:
        bm25_hits = self._bm25_hits(query, k)
        bm25_best: dict[str, tuple[float, str, str]] = {}
        bm25_ranking: list[str] = []
        for h in bm25_hits:
            if h.doc_id not in bm25_best:
                bm25_ranking.append(h.doc_id)
                bm25_best[h.doc_id] = (h.score, h.chunk_id, h.text)

        vector_ranking, vector_best = self._vector_hits(query, k)

        bm25_scores = {doc_id: score for doc_id, (score, _, _) in bm25_best.items()}
        vector_scores = {doc_id: score for doc_id, (score, _, _) in vector_best.items()}
        scores = self._fuse(query, bm25_ranking, bm25_scores, vector_ranking, vector_scores)
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
