"""Query-log and result-selection capture -- the real P3 day-1 deliverable.

This is infrastructure, not a trained model: it logs every search's ranked
candidates (with the per-candidate features a future reranker needs -- BM25
score, vector score, RRF score, source type, ingestion recency) and lets a
client report back which result got selected. `count_interactions()` is
what `ltr.train` checks against the roadmap's stated 500-1,000 minimum
before treating any of this as enough signal to train on -- see
`ltr/train.py` and `ltr/status.py`.

The API layer (src/api/main.py) holds ONE of these as a module-level
singleton across requests, and FastAPI runs each request in its own
threadpool worker thread -- so this connection gets used from a different
OS thread on every request, not just constructed once and read forever from
the same thread. `sqlite3.connect()` defaults to `check_same_thread=True`,
which raises on exactly that pattern (caught live via a test that made two
requests back-to-back and hit `sqlite3.ProgrammingError: SQLite objects
created in a thread can only be used in that same thread`). Fixed with
`check_same_thread=False` plus an explicit lock around every statement,
since disabling that check does NOT make sqlite3 connections safe for
actual concurrent use from multiple threads at once -- it only lifts the
same-thread requirement, the caller still has to serialize access itself.
"""
from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class CandidateRecord:
    doc_id: str
    chunk_id: str
    rank: int
    bm25_score: float | None
    vector_score: float | None
    rrf_score: float | None
    source_type: str | None
    ingested_at: str | None


class QueryLog:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS queries (
                query_id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_text TEXT NOT NULL,
                index_type TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS query_candidates (
                query_id INTEGER NOT NULL,
                doc_id TEXT NOT NULL,
                chunk_id TEXT,
                rank INTEGER NOT NULL,
                bm25_score REAL,
                vector_score REAL,
                rrf_score REAL,
                source_type TEXT,
                ingested_at TEXT,
                PRIMARY KEY (query_id, doc_id)
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS selections (
                selection_id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_id INTEGER NOT NULL,
                doc_id TEXT NOT NULL,
                chunk_id TEXT,
                rank_selected INTEGER,
                timestamp TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def log_query(self, query_text: str, index_type: str, candidates: list[CandidateRecord]) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO queries (query_text, index_type, timestamp) VALUES (?, ?, ?)",
                (query_text, index_type, datetime.now(timezone.utc).isoformat()),
            )
            query_id = cur.lastrowid
            self._conn.executemany(
                """
                INSERT INTO query_candidates
                    (query_id, doc_id, chunk_id, rank, bm25_score, vector_score, rrf_score, source_type, ingested_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (query_id, c.doc_id, c.chunk_id, c.rank, c.bm25_score, c.vector_score,
                     c.rrf_score, c.source_type, c.ingested_at)
                    for c in candidates
                ],
            )
            self._conn.commit()
            return query_id

    def log_selection(self, query_id: int, doc_id: str, chunk_id: str | None, rank_selected: int | None) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO selections (query_id, doc_id, chunk_id, rank_selected, timestamp) VALUES (?, ?, ?, ?, ?)",
                (query_id, doc_id, chunk_id, rank_selected, datetime.now(timezone.utc).isoformat()),
            )
            self._conn.commit()

    def count_queries(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM queries").fetchone()[0]

    def count_interactions(self) -> int:
        """A logged selection is one labeled training example -- this is the
        number the roadmap's 500-1,000 minimum is measured against, not raw
        query count (an unselected search carries no relevance signal)."""
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM selections").fetchone()[0]

    def training_rows(self) -> list[dict]:
        """One row per (query_id, candidate) for every query that has at
        least one selection, with a binary label: 1 if that candidate was the
        selected doc_id for its query, 0 otherwise. Rows are grouped by
        query_id in the returned order (required for LightGBM's group-based
        LambdaMART ranking objective)."""
        with self._lock:
            selected_by_query: dict[int, set[str]] = {}
            for query_id, doc_id in self._conn.execute("SELECT query_id, doc_id FROM selections"):
                selected_by_query.setdefault(query_id, set()).add(doc_id)

            rows = []
            for query_id in sorted(selected_by_query):
                candidates = self._conn.execute(
                    "SELECT doc_id, chunk_id, rank, bm25_score, vector_score, rrf_score, source_type, ingested_at "
                    "FROM query_candidates WHERE query_id = ? ORDER BY rank",
                    (query_id,),
                ).fetchall()
                for doc_id, chunk_id, rank, bm25, vector, rrf, source_type, ingested_at in candidates:
                    rows.append(
                        {
                            "query_id": query_id,
                            "doc_id": doc_id,
                            "chunk_id": chunk_id,
                            "rank": rank,
                            "bm25_score": bm25,
                            "vector_score": vector,
                            "rrf_score": rrf,
                            "source_type": source_type,
                            "ingested_at": ingested_at,
                            "label": 1 if doc_id in selected_by_query[query_id] else 0,
                        }
                    )
            return rows

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "QueryLog":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
