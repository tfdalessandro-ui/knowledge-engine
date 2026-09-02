"""CPU-friendly sentence embeddings (P2 tech choice: BGE-Small).

First use downloads the model from HuggingFace (~130MB, cached under
~/.cache/huggingface afterward) -- see the P2 network-dependency note in
HELP.md, same pattern as Docling's PDF OCR models in P1.
"""
from __future__ import annotations

import hashlib

import numpy as np

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384

_model = None  # lazy singleton; loading it is the expensive part


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_texts(texts: list[str]) -> np.ndarray:
    """L2-normalized float32 embeddings, shape (len(texts), EMBED_DIM).
    Normalized so inner-product search in FAISS is equivalent to cosine similarity."""
    if not texts:
        return np.zeros((0, EMBED_DIM), dtype="float32")
    vectors = _get_model().encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    return vectors.astype("float32")


def vector_id_for_chunk(chunk_id: str, text: str) -> int:
    """Stable int64 id derived from BOTH chunk_id and its text content --
    deliberately NOT position-only. HNSW can't remove_ids (see
    index_faiss.py), so a changed document is handled by tombstoning its old
    vectors and adding new ones; if an edited chunk kept the same doc_id and
    chunk_index, hashing position alone would reproduce the *same* id, and
    the registry's `INSERT OR REPLACE` on re-add would silently resurrect the
    just-tombstoned row while its stale vector stayed orphaned, uncounted,
    in the FAISS graph forever. Hashing the text too means any content change
    gets a genuinely fresh id, so the old row's tombstone sticks."""
    digest = hashlib.sha1(f"{chunk_id}||{text}".encode("utf-8")).hexdigest()
    return int(digest[:15], 16)  # 60 bits, comfortably within signed int64
