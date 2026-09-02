"""SQLite metadata for the FAISS vector index: maps a FAISS vector_id back to
(doc_id, chunk_id, text), and tracks which vectors are tombstoned (see
index_faiss.py for why deletion works this way instead of a real remove).

`check_same_thread=False` + an explicit lock: the API layer (P3, via
HybridIndex) holds one of these as a module-level singleton across requests,
and FastAPI runs each request in its own threadpool thread -- see the
identical, more detailed note in ltr/query_log.py.
"""
from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path


@dataclass
class VectorRecord:
    vector_id: int
    doc_id: str
    chunk_id: str
    chunk_index: int
    text: str


class VectorRegistry:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vectors (
                vector_id INTEGER PRIMARY KEY,
                doc_id TEXT NOT NULL,
                chunk_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                deleted INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_vectors_doc_id ON vectors(doc_id)")
        self._conn.commit()

    def add_chunks(self, doc_id: str, rows: list[tuple[int, str, int, str]]) -> None:
        """rows: list of (vector_id, chunk_id, chunk_index, text)."""
        with self._lock:
            self._conn.executemany(
                "INSERT OR REPLACE INTO vectors (vector_id, doc_id, chunk_id, chunk_index, text, deleted) "
                "VALUES (?, ?, ?, ?, ?, 0)",
                [(vid, doc_id, cid, cidx, text) for vid, cid, cidx, text in rows],
            )
            self._conn.commit()

    def tombstone_doc(self, doc_id: str) -> None:
        with self._lock:
            self._conn.execute("UPDATE vectors SET deleted = 1 WHERE doc_id = ?", (doc_id,))
            self._conn.commit()

    def get_active_by_ids(self, vector_ids: list[int]) -> dict[int, VectorRecord]:
        if not vector_ids:
            return {}
        with self._lock:
            placeholders = ",".join("?" for _ in vector_ids)
            rows = self._conn.execute(
                f"SELECT vector_id, doc_id, chunk_id, chunk_index, text FROM vectors "
                f"WHERE vector_id IN ({placeholders}) AND deleted = 0",
                vector_ids,
            ).fetchall()
            return {r[0]: VectorRecord(*r) for r in rows}

    def all_active(self) -> list[VectorRecord]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT vector_id, doc_id, chunk_id, chunk_index, text FROM vectors WHERE deleted = 0"
            ).fetchall()
            return [VectorRecord(*r) for r in rows]

    def hard_delete_tombstoned(self) -> int:
        with self._lock:
            cur = self._conn.execute("DELETE FROM vectors WHERE deleted = 1")
            self._conn.commit()
            return cur.rowcount

    def tombstone_ratio(self) -> float:
        with self._lock:
            total, deleted = self._conn.execute(
                "SELECT COUNT(*), SUM(deleted) FROM vectors"
            ).fetchone()
            if not total:
                return 0.0
            return (deleted or 0) / total

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "VectorRegistry":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
