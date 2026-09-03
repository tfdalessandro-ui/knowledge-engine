import pytest

from kg.graph_store import MemgraphStore

pytestmark = pytest.mark.requires_memgraph


@pytest.fixture()
def store():
    s = MemgraphStore()
    s.clear()
    yield s
    s.clear()
    s.close()


def test_upsert_entity_and_count(store):
    store.upsert_entity("TECHNOLOGY:bm25", "BM25", "TECHNOLOGY", "doc1")
    assert store.entity_count() == 1


def test_upsert_entity_rejects_unknown_label(store):
    with pytest.raises(ValueError):
        store.upsert_entity("X:y", "y", "NOT_A_REAL_LABEL", "doc1")


def test_repeated_upsert_increments_mention_count(store):
    store.upsert_entity("TECHNOLOGY:bm25", "BM25", "TECHNOLOGY", "doc1")
    store.upsert_entity("TECHNOLOGY:bm25", "BM25", "TECHNOLOGY", "doc2")
    with store._driver.session() as session:
        count = session.run(
            "MATCH (e:Entity {canonical_id: 'TECHNOLOGY:bm25'}) RETURN e.mention_count AS c"
        ).single()["c"]
    assert count == 2


def test_upsert_relation_and_get_neighbors(store):
    store.upsert_entity("TECHNOLOGY:tantivy", "Tantivy", "TECHNOLOGY", "doc1")
    store.upsert_entity("TECHNOLOGY:bm25", "BM25", "TECHNOLOGY", "doc1")
    store.upsert_relation("TECHNOLOGY:tantivy", "USES", "TECHNOLOGY:bm25")

    neighbors = store.get_neighbors("TECHNOLOGY:tantivy")
    assert len(neighbors) == 1
    assert neighbors[0].name == "BM25"
    assert neighbors[0].relation == "USES"
    assert neighbors[0].direction == "outgoing"

    reverse = store.get_neighbors("TECHNOLOGY:bm25")
    assert reverse[0].direction == "incoming"


def test_upsert_relation_rejects_unknown_type(store):
    store.upsert_entity("TECHNOLOGY:a", "A", "TECHNOLOGY", "doc1")
    store.upsert_entity("TECHNOLOGY:b", "B", "TECHNOLOGY", "doc1")
    with pytest.raises(ValueError):
        store.upsert_relation("TECHNOLOGY:a", "NOT_A_REAL_RELATION", "TECHNOLOGY:b")


def test_entity_with_no_relations_has_no_neighbors(store):
    store.upsert_entity("TECHNOLOGY:isolated", "Isolated", "TECHNOLOGY", "doc1")
    assert store.get_neighbors("TECHNOLOGY:isolated") == []
