"""Ingestion pipeline: scan a corpus directory, parse + chunk anything new or
changed, and update the BM25 index incrementally. Unchanged files are
skipped entirely -- neither re-parsed nor re-chunked nor touched in the
index -- which is what makes this "incremental" rather than a rebuild that
happens to be fast.

doc_id is the file's stem (filename without extension), matching how the P0
judgment set references documents (e.g. `doc01_bm25.txt` -> `doc01_bm25`).
This means corpus filenames must be unique by stem across the whole corpus
directory tree; that's a reasonable constraint for a single-corpus P1 MVP,
revisit if/when multiple corpora need distinct namespaces.
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
    skipped_unsupported: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def touched(self) -> int:
        """Files that actually caused index work (i.e. NOT a full rebuild)."""
        return self.added + self.updated + self.removed


def _iter_corpus_files(corpus_dir: Path):
    for path in sorted(corpus_dir.rglob("*")):
        if path.is_file():
            yield path


def run_ingest(corpus_dir: Path, index_dir: Path, registry_db: Path) -> IngestReport:
    report = IngestReport()
    index = BM25Index(index_dir)

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
                report.updated += 1
            else:
                report.added += 1

            index.add_chunks(doc_id, chunks)
            registry.upsert(rel_path, doc_id, new_hash, len(chunks))

        stale_paths = registry.all_paths() - seen_paths
        for rel_path in stale_paths:
            record = registry.get(rel_path)
            if record is not None:
                index.delete_doc(record.doc_id)
                registry.delete(rel_path)
                report.removed += 1

    index.commit()
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from config import get_settings

    parser = argparse.ArgumentParser(description="Run the incremental ingestion pipeline")
    parser.add_argument("--corpus", type=Path, default=None)
    args = parser.parse_args(argv)

    settings = get_settings()
    corpus_dir = args.corpus or settings.corpus_dir
    report = run_ingest(corpus_dir, settings.tantivy_index_dir, settings.registry_db_path)

    print(f"scanned={report.scanned} unchanged={report.unchanged} added={report.added} "
          f"updated={report.updated} removed={report.removed}")
    if report.skipped_unsupported:
        print(f"skipped (unsupported extension): {report.skipped_unsupported}")
    if report.errors:
        print(f"errors: {report.errors}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
