import pytest

from config import get_settings
from kg.graph_store import MemgraphStore
from kg.pipeline import run_kg_extraction

pytestmark = pytest.mark.requires_memgraph


@pytest.fixture()
def clean_graph():
    # Isolated test instance -- MemgraphStore() with no args defaults to
    # production (127.0.0.1:7687); this fixture clear()s in setup AND
    # teardown, so it must never use that default. See TODO.md item 5.
    store = MemgraphStore(get_settings().test_memgraph_uri)
    store.clear()
    yield store
    store.clear()
    store.close()


def _make_corpus(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.txt").write_text("Tantivy uses BM25 for ranking.", encoding="utf-8")
    (corpus / "b.txt").write_text("Hetzner offers the CCX23 instance.", encoding="utf-8")
    return corpus


def test_pipeline_extracts_entities_and_relations(tmp_path, clean_graph):
    corpus = _make_corpus(tmp_path)
    report = run_kg_extraction(corpus, get_settings().test_memgraph_uri, tmp_path / "merge_review.db")

    assert report.documents_processed == 2
    assert report.entities_extracted == 4  # Tantivy, BM25, Hetzner, CCX23
    assert report.relations_extracted == 2
    assert not report.errors


def test_pipeline_writes_to_memgraph(tmp_path, clean_graph):
    corpus = _make_corpus(tmp_path)
    run_kg_extraction(corpus, get_settings().test_memgraph_uri, tmp_path / "merge_review.db")

    assert clean_graph.entity_count() == 4
    neighbors = clean_graph.get_neighbors("TECHNOLOGY:tantivy")
    assert len(neighbors) == 1
    assert neighbors[0].name == "BM25"
