"""Uses synthetic vectors, not the real embedding model -- keeps this test
fast and offline. Real embedding integration is covered separately in
test_pipeline_vectors.py."""
import numpy as np

from ingest.embeddings import EMBED_DIM
from ingest.index_faiss import VectorIndex


def _unit_vectors(n: int) -> np.ndarray:
    rng = np.random.default_rng(42)
    v = rng.random((n, EMBED_DIM), dtype="float32")
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    return v


def test_add_and_search_returns_self_as_top_hit(tmp_path):
    idx = VectorIndex(tmp_path / "index.faiss")
    vecs = _unit_vectors(5)
    ids = np.array([10, 11, 12, 13, 14], dtype="int64")
    idx.add(ids, vecs)
    scores, hit_ids = idx.search(vecs[0], limit=3)
    assert hit_ids[0] == 10
    assert scores[0] > 0.99  # cosine similarity of a vector with itself


def test_persist_and_reload(tmp_path):
    path = tmp_path / "index.faiss"
    idx = VectorIndex(path)
    vecs = _unit_vectors(3)
    ids = np.array([1, 2, 3], dtype="int64")
    idx.add(ids, vecs)
    idx.save()

    reloaded = VectorIndex(path)
    assert reloaded.ntotal == 3
    _, hit_ids = reloaded.search(vecs[1], limit=1)
    assert hit_ids[0] == 2


def test_rebuild_replaces_contents(tmp_path):
    idx = VectorIndex(tmp_path / "index.faiss")
    vecs = _unit_vectors(4)
    idx.add(np.array([1, 2, 3, 4], dtype="int64"), vecs)
    assert idx.ntotal == 4

    idx.rebuild(np.array([100, 101], dtype="int64"), vecs[:2])
    assert idx.ntotal == 2
    _, hit_ids = idx.search(vecs[0], limit=5)
    assert set(int(i) for i in hit_ids if i != -1) <= {100, 101}


def test_empty_index_search_returns_empty(tmp_path):
    idx = VectorIndex(tmp_path / "index.faiss")
    scores, ids = idx.search(_unit_vectors(1)[0], limit=5)
    assert len(scores) == 0
    assert len(ids) == 0
