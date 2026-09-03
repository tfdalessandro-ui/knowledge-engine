"""P4 exit criterion: correct neighbor retrieval on a fixed 20-entity test
set. Runs the real KG pipeline over the real data/corpus/ into Memgraph,
then checks a fixed, hand-verified set of 20 entities (11 with real
relations, 9 correctly isolated) against their expected neighbors -- values
below were derived by manually reading `kg.pipeline`'s actual output against
the corpus text (see LOGBOOK for the full manual spot-check), not assumed.
"""
from pathlib import Path

import pytest

from config import get_settings
from kg.graph_store import MemgraphStore
from kg.pipeline import run_kg_extraction

pytestmark = pytest.mark.requires_memgraph

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = REPO_ROOT / "data" / "corpus"

# canonical_id -> {(neighbor_name, relation, direction), ...}
FIXED_TEST_SET = {
    "TECHNOLOGY:sqlite": {("FTS5", "PROVIDES", "outgoing")},
    "TECHNOLOGY:fts5": {("SQLite", "PROVIDES", "incoming")},
    "TECHNOLOGY:fastapi": {("Starlette", "RUNS_ON", "outgoing"), ("Pydantic", "USES", "outgoing")},
    "TECHNOLOGY:starlette": {("FastAPI", "RUNS_ON", "incoming")},
    "TECHNOLOGY:pydantic": {("FastAPI", "USES", "incoming")},
    "COMPANY:hetzner": {("CCX23", "OFFERS", "outgoing")},
    "PRODUCT:ccx23": {("Hetzner", "OFFERS", "incoming")},
    "TECHNOLOGY:tantivy": {("BM25", "USES", "outgoing")},
    "TECHNOLOGY:bm25": {("Tantivy", "USES", "incoming")},
    "TECHNOLOGY:docker": {("Memgraph", "RUNS_ON", "outgoing")},
    "TECHNOLOGY:memgraph": {("Docker", "RUNS_ON", "incoming")},
    # correctly isolated -- mentioned in the corpus, but never co-occur with
    # another curated entity in a sentence our relation extractor can use
    "TECHNOLOGY:tf idf": set(),
    "TECHNOLOGY:ndcg": set(),
    "TECHNOLOGY:mrr": set(),
    "TECHNOLOGY:hnsw": set(),
    "TECHNOLOGY:faiss": set(),
    "TECHNOLOGY:docling": set(),
    "TECHNOLOGY:python": set(),
    "TECHNOLOGY:ubuntu": set(),
    "TECHNOLOGY:spacy": set(),
}


@pytest.fixture(scope="module")
def populated_store():
    settings = get_settings()
    store = MemgraphStore(settings.memgraph_uri)
    store.clear()
    run_kg_extraction(CORPUS_DIR, settings.memgraph_uri, settings.merge_review_db_path)
    yield store
    store.clear()
    store.close()


def test_fixed_20_entity_set_size():
    assert len(FIXED_TEST_SET) == 20


@pytest.mark.parametrize("canonical_id,expected", FIXED_TEST_SET.items())
def test_neighbor_retrieval_matches_hand_verified_expectation(populated_store, canonical_id, expected):
    neighbors = populated_store.get_neighbors(canonical_id)
    actual = {(n.name, n.relation, n.direction) for n in neighbors}
    assert actual == expected, f"{canonical_id}: expected {expected}, got {actual}"
