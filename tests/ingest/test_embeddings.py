"""Uses the real BGE-Small model -- downloads it on first run (~130MB,
cached afterward). Not gated behind a flag like the PDF test: embeddings are
P2's actual deliverable, not an optional format, so P2's default test run
does need network once. See the P2 note in requirements.txt / HELP.md.
"""
import numpy as np

from ingest.embeddings import EMBED_DIM, embed_texts, vector_id_for_chunk


def test_embed_texts_shape_and_normalization():
    vectors = embed_texts(["hello world", "bm25 ranking function"])
    assert vectors.shape == (2, EMBED_DIM)
    assert vectors.dtype == np.float32
    norms = np.linalg.norm(vectors, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-4)


def test_embed_texts_empty_list():
    vectors = embed_texts([])
    assert vectors.shape == (0, EMBED_DIM)


def test_similar_texts_are_closer_than_dissimilar():
    a, b, c = embed_texts(["a dog ran in the park", "a puppy played outside", "quarterly tax filing deadline"])
    sim_ab = float(np.dot(a, b))
    sim_ac = float(np.dot(a, c))
    assert sim_ab > sim_ac


def test_vector_id_for_chunk_is_deterministic():
    assert vector_id_for_chunk("doc1::0", "hello") == vector_id_for_chunk("doc1::0", "hello")


def test_vector_id_for_chunk_differs_for_different_positions():
    assert vector_id_for_chunk("doc1::0", "hello") != vector_id_for_chunk("doc1::1", "hello")


def test_vector_id_for_chunk_differs_when_text_changes_at_same_position():
    # this is the whole point: an edited chunk at the same doc_id/index must
    # get a fresh id, or a tombstoned row gets silently resurrected on re-add
    assert vector_id_for_chunk("doc1::0", "old text") != vector_id_for_chunk("doc1::0", "new text")


def test_vector_id_for_chunk_fits_int64():
    vid = vector_id_for_chunk("some::chunk::id", "some text")
    assert 0 <= vid < 2**63
