"""Vector index over document chunks, backed by FAISS HNSW (the P2 tech
choice), no separate service.

KNOWN LIMITATION, confirmed directly against faiss 1.15.0 rather than
assumed: HNSW does not support `remove_ids` --
`RuntimeError: remove_ids not implemented for this type of index`. Unlike
Tantivy (P1), which can cleanly delete-then-readd a changed document, this
index can only ever grow. Incremental updates are handled by *tombstoning*
a changed/removed document's old vectors in the metadata registry
(`VectorRegistry.tombstone_doc`) -- they stay physically in the FAISS graph
but are filtered out of every search result -- and periodically compacting
(rebuilding the index from only the live vectors) once the tombstoned
fraction crosses a threshold. This is a standard, accepted pattern for
HNSW-family indexes; see `PipelineReport.compacted` for when it fires.
"""
from __future__ import annotations

from pathlib import Path

import faiss
import numpy as np

from ingest.embeddings import EMBED_DIM

HNSW_M = 32  # HNSW graph connectivity; faiss default-adjacent, fine for a small-to-medium corpus


def _new_hnsw_index() -> "faiss.IndexIDMap2":
    hnsw = faiss.IndexHNSWFlat(EMBED_DIM, HNSW_M, faiss.METRIC_INNER_PRODUCT)
    return faiss.IndexIDMap2(hnsw)


class VectorIndex:
    def __init__(self, index_path: Path):
        self.index_path = index_path
        index_path.parent.mkdir(parents=True, exist_ok=True)
        if index_path.exists():
            self._index = faiss.read_index(str(index_path))
        else:
            self._index = _new_hnsw_index()

    def add(self, vector_ids: np.ndarray, vectors: np.ndarray) -> None:
        if len(vector_ids) == 0:
            return
        self._index.add_with_ids(vectors, vector_ids)

    def search(self, query_vector: np.ndarray, limit: int) -> tuple[np.ndarray, np.ndarray]:
        """Returns (scores, vector_ids), both shape (limit,). A miss slot is
        vector_id == -1 (fewer than `limit` results, e.g. tiny index)."""
        if self._index.ntotal == 0:
            return np.array([]), np.array([])
        scores, ids = self._index.search(query_vector.reshape(1, -1), limit)
        return scores[0], ids[0]

    def rebuild(self, vector_ids: np.ndarray, vectors: np.ndarray) -> None:
        """Replace the index contents entirely -- used for compaction, to
        physically drop tombstoned vectors instead of just filtering them at
        query time forever."""
        self._index = _new_hnsw_index()
        self.add(vector_ids, vectors)

    def save(self) -> None:
        faiss.write_index(self._index, str(self.index_path))

    @property
    def ntotal(self) -> int:
        return self._index.ntotal
