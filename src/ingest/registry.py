"""SQLite-backed record of what's already indexed: path -> content hash and
chunk count. This is what makes incremental re-indexing possible -- the
pipeline diffs the corpus against this table instead of re-parsing everything
on every run.

`source_type` and `ingested_at` (added in P3) are LTR features, not
indexing-diff state -- looked up per-doc when logging a search's candidates,
since a future reranker needs "how recently was this ingested" and "what
kind of document is this" as signals alongside BM25/vector scores.

`check_same_thread=False` + an explicit lock: the API layer (P3) holds one
of these as a module-level singleton across requests, and FastAPI runs each
request in its own threadpool thread -- see the identical, more detailed
note in ltr/query_log.py for why a bare sqlite3 connection breaks under that
pattern and why disabling the same-thread check alone isn't sufficient.
"""
from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class DocumentRecord:
    path: str
    doc_id: str
    content_hash: str
    chunk_count: int
    source_type: str | None = None
    ingested_at: str | None = None


class DocumentRegistry:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                path TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                chunk_count INTEGER NOT NULL,
                source_type TEXT,
                ingested_at TEXT
            )
            """
        )
        for column in ("source_type TEXT", "ingested_at TEXT"):  # migration for pre-P3 DBs
            try:
                self._conn.execute(f"ALTER TABLE documents ADD COLUMN {column}")
            except sqlite3.OperationalError:
                pass  # column already exists
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_doc_id ON documents(doc_id)")
        self._conn.commit()

    def get(self, path: str) -> DocumentRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT path, doc_id, content_hash, chunk_count, source_type, ingested_at "
                "FROM documents WHERE path = ?",
                (path,),
            ).fetchone()
            return DocumentRecord(*row) if row else None

    def get_by_doc_id(self, doc_id: str) -> DocumentRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT path, doc_id, content_hash, chunk_count, source_type, ingested_at "
                "FROM documents WHERE doc_id = ?",
                (doc_id,),
            ).fetchone()
            return DocumentRecord(*row) if row else None

    def upsert(
        self,
        path: str,
        doc_id: str,
        content_hash: str,
        chunk_count: int,
        source_type: str | None = None,
        ingested_at: str | None = None,
    ) -> None:
        ingested_at = ingested_at or datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO documents (path, doc_id, content_hash, chunk_count, source_type, ingested_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    doc_id=excluded.doc_id, content_hash=excluded.content_hash, chunk_count=excluded.chunk_count,
                    source_type=excluded.source_type, ingested_at=excluded.ingested_at
                """,
                (path, doc_id, content_hash, chunk_count, source_type, ingested_at),
            )
            self._conn.commit()

    def delete(self, path: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM documents WHERE path = ?", (path,))
            self._conn.commit()

    def all_paths(self) -> set[str]:
        with self._lock:
            return {row[0] for row in self._conn.execute("SELECT path FROM documents")}

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "DocumentRegistry":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
