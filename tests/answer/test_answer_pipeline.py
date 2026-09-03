"""Real end-to-end test of the P7 answer layer: real retrieval, real model
inference, real citation validation. Kept to a small number of queries --
CPU inference with a 3B model is genuinely slow (see the P7 logbook for
measured latency), and this is deliberately not part of the fast default
suite's spirit even though it runs when the model is available.
"""
import pytest

from answer.pipeline import AnswerEngine
from config import get_settings
from eval.hybrid_index import HybridIndex
from ingest.pipeline import run_ingest

pytestmark = pytest.mark.requires_llm


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    corpus = tmp_path_factory.mktemp("answer_corpus")
    (corpus / "bm25.txt").write_text(
        "BM25 is a bag-of-words ranking function used by search engines. "
        "It was developed as an improvement over TF-IDF.",
        encoding="utf-8",
    )
    (corpus / "unrelated.txt").write_text(
        "Bananas are a good source of potassium and are commonly grown in tropical climates.",
        encoding="utf-8",
    )

    tmp_dir = tmp_path_factory.mktemp("answer_index")
    run_ingest(
        corpus, tmp_dir / "index", tmp_dir / "registry.db",
        vector_index_path=tmp_dir / "vectors" / "index.faiss", vector_registry_db=tmp_dir / "vectors.db",
    )
    index = HybridIndex(tmp_dir / "index", tmp_dir / "vectors" / "index.faiss", tmp_dir / "vectors.db")

    settings = get_settings()
    return AnswerEngine(index, settings.llm_model_path, n_ctx=settings.llm_n_ctx, max_tokens=256)


def test_answer_cites_a_real_retrieved_chunk(engine):
    result = engine.answer("What is BM25?", k=3)
    assert "bm25" in result.answer_text.lower()
    assert result.citation_check.has_any_citation is True
    assert result.citation_check.all_valid is True


def test_all_citations_trace_to_retrieved_chunks(engine):
    result = engine.answer("What is BM25 an improvement over?", k=3)
    for citation in result.citation_check.citations_found:
        assert citation in result.retrieved_chunk_ids
