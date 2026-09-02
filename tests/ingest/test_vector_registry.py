from ingest.vector_registry import VectorRegistry


def test_add_and_get_active_by_ids(tmp_path):
    reg = VectorRegistry(tmp_path / "vectors.db")
    reg.add_chunks("doc1", [(1, "doc1::0", 0, "hello"), (2, "doc1::1", 1, "world")])
    records = reg.get_active_by_ids([1, 2, 999])
    assert set(records) == {1, 2}
    assert records[1].text == "hello"
    assert records[1].doc_id == "doc1"


def test_tombstone_removes_from_active(tmp_path):
    reg = VectorRegistry(tmp_path / "vectors.db")
    reg.add_chunks("doc1", [(1, "doc1::0", 0, "hello")])
    reg.tombstone_doc("doc1")
    assert reg.get_active_by_ids([1]) == {}
    assert reg.all_active() == []


def test_tombstone_ratio(tmp_path):
    reg = VectorRegistry(tmp_path / "vectors.db")
    reg.add_chunks("doc1", [(1, "doc1::0", 0, "a"), (2, "doc1::1", 1, "b")])
    reg.add_chunks("doc2", [(3, "doc2::0", 0, "c"), (4, "doc2::1", 1, "d")])
    assert reg.tombstone_ratio() == 0.0
    reg.tombstone_doc("doc1")
    assert reg.tombstone_ratio() == 0.5


def test_hard_delete_tombstoned(tmp_path):
    reg = VectorRegistry(tmp_path / "vectors.db")
    reg.add_chunks("doc1", [(1, "doc1::0", 0, "a")])
    reg.add_chunks("doc2", [(2, "doc2::0", 0, "b")])
    reg.tombstone_doc("doc1")
    removed = reg.hard_delete_tombstoned()
    assert removed == 1
    assert reg.tombstone_ratio() == 0.0
    assert len(reg.all_active()) == 1


def test_add_chunks_replaces_on_reingest(tmp_path):
    reg = VectorRegistry(tmp_path / "vectors.db")
    reg.add_chunks("doc1", [(1, "doc1::0", 0, "old text")])
    reg.add_chunks("doc1", [(1, "doc1::0", 0, "new text")])
    records = reg.get_active_by_ids([1])
    assert records[1].text == "new text"
