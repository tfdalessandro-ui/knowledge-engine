"""Vector-index side of the incremental pipeline: add/update/tombstone and
compaction. Uses the real embedding model (network on first run, see
test_embeddings.py docstring)."""
from pathlib import Path

from ingest.pipeline import run_ingest
from ingest.vector_registry import VectorRegistry


def _make_corpus(tmp_path: Path) -> Path:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "alpha.txt").write_text("alpha document about apples and orchards", encoding="utf-8")
    (corpus / "beta.txt").write_text("beta document about bicycles and gears", encoding="utf-8")
    return corpus


def _run(tmp_path, corpus, compact_threshold=0.2):
    return run_ingest(
        corpus,
        tmp_path / "index",
        tmp_path / "registry.db",
        vector_index_path=tmp_path / "vectors" / "index.faiss",
        vector_registry_db=tmp_path / "vectors.db",
        vector_compact_threshold=compact_threshold,
    )


def test_first_run_builds_vectors(tmp_path):
    corpus = _make_corpus(tmp_path)
    report = _run(tmp_path, corpus)
    assert report.vectors_added == 2  # one chunk per short doc
    reg = VectorRegistry(tmp_path / "vectors.db")
    assert len(reg.all_active()) == 2


def test_unchanged_run_adds_no_vectors(tmp_path):
    corpus = _make_corpus(tmp_path)
    _run(tmp_path, corpus)
    report = _run(tmp_path, corpus)
    assert report.vectors_added == 0
    assert report.unchanged == 2


def test_editing_a_file_tombstones_old_vectors(tmp_path):
    corpus = _make_corpus(tmp_path)
    _run(tmp_path, corpus, compact_threshold=1.1)  # disable auto-compaction for this assertion
    (corpus / "beta.txt").write_text("beta document now about balloons entirely", encoding="utf-8")
    report = _run(tmp_path, corpus, compact_threshold=1.1)

    assert report.vectors_added == 1
    reg = VectorRegistry(tmp_path / "vectors.db")
    active_texts = {r.text for r in reg.all_active()}
    assert "balloons" in " ".join(active_texts)
    assert reg.tombstone_ratio() > 0  # old beta chunk is tombstoned, not gone


def test_compaction_fires_above_threshold(tmp_path):
    corpus = _make_corpus(tmp_path)
    _run(tmp_path, corpus, compact_threshold=0.2)
    (corpus / "beta.txt").write_text("beta document now entirely about balloons", encoding="utf-8")
    report = _run(tmp_path, corpus, compact_threshold=0.2)  # 1 tombstoned / 2 total = 0.5 > 0.2

    assert report.compacted is True
    reg = VectorRegistry(tmp_path / "vectors.db")
    assert reg.tombstone_ratio() == 0.0  # compaction hard-deletes tombstoned rows
