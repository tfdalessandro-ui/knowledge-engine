"""Exit criterion: a changed file re-indexes without a full rebuild.

Proven by running the pipeline twice over a small corpus, mutating one file
in between, and asserting the second run's report shows exactly one
`updated` doc and N-1 `unchanged` docs -- not N re-parsed/re-added docs,
which is what a full rebuild would look like.
"""
from pathlib import Path

from ingest.index_tantivy import BM25Index
from ingest.pipeline import run_ingest


def _make_corpus(tmp_path: Path) -> Path:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "alpha.txt").write_text("alpha document about apples and orchards", encoding="utf-8")
    (corpus / "beta.txt").write_text("beta document about bicycles and gears", encoding="utf-8")
    (corpus / "gamma.txt").write_text("gamma document about glaciers and ice", encoding="utf-8")
    return corpus


def test_first_run_adds_every_document(tmp_path):
    corpus = _make_corpus(tmp_path)
    report = run_ingest(corpus, tmp_path / "index", tmp_path / "registry.db")
    assert report.scanned == 3
    assert report.added == 3
    assert report.unchanged == 0
    assert report.updated == 0
    assert report.removed == 0


def test_second_run_with_no_changes_touches_nothing(tmp_path):
    corpus = _make_corpus(tmp_path)
    run_ingest(corpus, tmp_path / "index", tmp_path / "registry.db")
    report = run_ingest(corpus, tmp_path / "index", tmp_path / "registry.db")
    assert report.unchanged == 3
    assert report.touched() == 0


def test_editing_one_file_only_updates_that_one(tmp_path):
    corpus = _make_corpus(tmp_path)
    index_dir = tmp_path / "index"
    registry_db = tmp_path / "registry.db"
    run_ingest(corpus, index_dir, registry_db)

    (corpus / "beta.txt").write_text("beta document now about balloons and bicycles", encoding="utf-8")
    report = run_ingest(corpus, index_dir, registry_db)

    assert report.updated == 1
    assert report.unchanged == 2
    assert report.added == 0
    assert report.touched() == 1  # NOT 3 -- proves this isn't a full rebuild

    index = BM25Index(index_dir)
    hits = index.search("balloons", limit=10)
    assert any(h.doc_id == "beta" for h in hits)
    old_hits = index.search("gears", limit=10)
    assert any(h.doc_id == "beta" for h in old_hits) is False  # old content was replaced, not appended


def test_removing_a_file_removes_it_from_the_index(tmp_path):
    corpus = _make_corpus(tmp_path)
    index_dir = tmp_path / "index"
    registry_db = tmp_path / "registry.db"
    run_ingest(corpus, index_dir, registry_db)

    (corpus / "gamma.txt").unlink()
    report = run_ingest(corpus, index_dir, registry_db)

    assert report.removed == 1
    assert report.unchanged == 2

    index = BM25Index(index_dir)
    hits = index.search("glaciers", limit=10)
    assert all(h.doc_id != "gamma" for h in hits)


def test_adding_a_new_file_only_adds_that_one(tmp_path):
    corpus = _make_corpus(tmp_path)
    index_dir = tmp_path / "index"
    registry_db = tmp_path / "registry.db"
    run_ingest(corpus, index_dir, registry_db)

    (corpus / "delta.txt").write_text("delta document about deserts and dunes", encoding="utf-8")
    report = run_ingest(corpus, index_dir, registry_db)

    assert report.added == 1
    assert report.unchanged == 3
    assert report.touched() == 1
