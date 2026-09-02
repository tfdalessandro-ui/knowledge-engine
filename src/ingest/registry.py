"""SQLite-backed record of what's already indexed: path -> content hash and
chunk count. This is what makes incremental re-indexing possible -- the
pipeline diffs the corpus against this table instead of re-parsing everything
on every run.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DocumentRecord:
    path: str
    doc_id: str
    content_hash: str
    chunk_count: int


class DocumentRegistry:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                path TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                chunk_count INTEGER NOT NULL
            )
            """
        )
        self._conn.commit()

    def get(self, path: str) -> DocumentRecord | None:
        row = self._conn.execute(
            "SELECT path, doc_id, content_hash, chunk_count FROM documents WHERE path = ?", (path,)
        ).fetchone()
        return DocumentRecord(*row) if row else None

    def upsert(self, path: str, doc_id: str, content_hash: str, chunk_count: int) -> None:
        self._conn.execute(
            """
            INSERT INTO documents (path, doc_id, content_hash, chunk_count)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                doc_id=excluded.doc_id, content_hash=excluded.content_hash, chunk_count=excluded.chunk_count
            """,
            (path, doc_id, content_hash, chunk_count),
        )
        self._conn.commit()

    def delete(self, path: str) -> None:
        self._conn.execute("DELETE FROM documents WHERE path = ?", (path,))
        self._conn.commit()

    def all_paths(self) -> set[str]:
        return {row[0] for row in self._conn.execute("SELECT path FROM documents")}

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "DocumentRegistry":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
