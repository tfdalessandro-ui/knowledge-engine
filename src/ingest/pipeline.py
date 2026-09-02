"""Ingestion pipeline: scan a corpus directory, parse + chunk anything new or
changed, and update the BM25 index (P1) and, optionally, the vector index
(P2) incrementally. Unchanged files are skipped entirely -- neither
re-parsed nor re-chunked nor touched in either index -- which is what makes
this "incremental" rather than a rebuild that happens to be fast.

doc_id is the file's stem (filename without extension), matching how the P0
judgment set references documents (e.g. `doc01_bm25.txt` -> `doc01_bm25`).
This means corpus filenames must be unique by stem across the whole corpus
directory tree; that's a reasonable constraint for a single-corpus MVP,
revisit if/when multiple corpora need distinct namespaces.

Vector-index params (`vector_index_path`/`vector_registry_db`) are optional:
omit both to get P1's original BM25-only behavior (used by the P1 tests,
which stay fast and offline). The CLI (`main()`) always passes them, since
real usage builds both indices together.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ingest.chunking import chunk_text
from ingest.hashing import content_hash
from ingest.index_tantivy import BM25Index
from ingest.parsers import SUPPORTED_EXTENSIONS, parse_to_text
from ingest.registry import DocumentRegistry


@dataclass
class IngestReport:
    scanned: int = 0
    unchanged: int = 0
    added: int = 0
    updated: int = 0
    removed: int = 0
    vectors_added: int = 0
    compacted: bool = False
    skipped_unsupported: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def touched(self) -> int:
        """Files that actually caused index work (i.e. NOT a full rebuild)."""
        return self.added + self.updated + self.removed


def _iter_corpus_files(corpus_dir: Path):
    for path in sorted(corpus_dir.rglob("*")):
        if path.is_file():
            yield path


def run_ingest(
    corpus_dir: Path,
    index_dir: Path,
    registry_db: Path,
    vector_index_path: Path | None = None,
    vector_registry_db: Path | None = None,
    vector_compact_threshold: float = 0.2,
) -> IngestReport:
    report = IngestReport()
    index = BM25Index(index_dir)

    build_vectors = vector_index_path is not None and vector_registry_db is not None
    vector_index = None
    vector_registry = None
    if build_vectors:
        from ingest.embeddings import embed_texts, vector_id_for_chunk
        from ingest.index_faiss import VectorIndex
        from ingest.vector_registry import VectorRegistry

        vector_index = VectorIndex(vector_index_path)
        vector_registry = VectorRegistry(vector_registry_db)

    with DocumentRegistry(registry_db) as registry:
        seen_paths: set[str] = set()

        for path in _iter_corpus_files(corpus_dir):
            rel_path = str(path.relative_to(corpus_dir))
            ext = path.suffix.lower()

            if ext not in SUPPORTED_EXTENSIONS:
                report.skipped_unsupported.append(rel_path)
                continue

            report.scanned += 1
            seen_paths.add(rel_path)
            doc_id = path.stem
            new_hash = content_hash(path)
            existing = registry.get(rel_path)

            if existing is not None and existing.content_hash == new_hash:
                report.unchanged += 1
                continue

            try:
                text = parse_to_text(path)
            except Exception as exc:  # noqa: BLE001 - report and continue, don't abort the whole run
                report.errors.append(f"{rel_path}: {exc}")
                continue

            chunks = chunk_text(text)

            if existing is not None:
                index.delete_doc(doc_id)
                if build_vectors:
                    vector_registry.tombstone_doc(doc_id)  # HNSW can't remove_ids; see index_faiss.py
                report.updated += 1
            else:
                report.added += 1

            index.add_chunks(doc_id, chunks)
            registry.upsert(rel_path, doc_id, new_hash, len(chunks), source_type=ext.lstrip("."))

            if build_vectors and chunks:
                chunk_ids = [f"{doc_id}::{i}" for i in range(len(chunks))]
                vector_ids = [vector_id_for_chunk(cid, text) for cid, text in zip(chunk_ids, chunks)]
                vectors = embed_texts(chunks)
                import numpy as np

                vector_index.add(np.array(vector_ids, dtype="int64"), vectors)
                vector_registry.add_chunks(
                    doc_id, list(zip(vector_ids, chunk_ids, range(len(chunks)), chunks))
                )
                report.vectors_added += len(chunks)

        stale_paths = registry.all_paths() - seen_paths
        for rel_path in stale_paths:
            record = registry.get(rel_path)
            if record is not None:
                index.delete_doc(record.doc_id)
                if build_vectors:
                    vector_registry.tombstone_doc(record.doc_id)
                registry.delete(rel_path)
                report.removed += 1

    index.commit()

    if build_vectors:
        if vector_registry.tombstone_ratio() > vector_compact_threshold:
            import numpy as np

            live = vector_registry.all_active()
            if live:
                ids = np.array([r.vector_id for r in live], dtype="int64")
                vectors = embed_texts([r.text for r in live])
                vector_index.rebuild(ids, vectors)
            vector_registry.hard_delete_tombstoned()
            report.compacted = True
        vector_index.save()
        vector_registry.close()

    return report


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from config import get_settings

    parser = argparse.ArgumentParser(description="Run the incremental ingestion pipeline")
    parser.add_argument("--corpus", type=Path, default=None)
    parser.add_argument("--no-vectors", action="store_true", help="skip embedding/vector-index maintenance (BM25 only)")
    args = parser.parse_args(argv)

    settings = get_settings()
    corpus_dir = args.corpus or settings.corpus_dir
    report = run_ingest(
        corpus_dir,
        settings.tantivy_index_dir,
        settings.registry_db_path,
        vector_index_path=None if args.no_vectors else settings.faiss_index_path,
        vector_registry_db=None if args.no_vectors else settings.vector_registry_db_path,
        vector_compact_threshold=settings.vector_compact_threshold,
    )

    print(f"scanned={report.scanned} unchanged={report.unchanged} added={report.added} "
          f"updated={report.updated} removed={report.removed} vectors_added={report.vectors_added} "
          f"compacted={report.compacted}")
    if report.skipped_unsupported:
        print(f"skipped (unsupported extension): {report.skipped_unsupported}")
    if report.errors:
        print(f"errors: {report.errors}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
