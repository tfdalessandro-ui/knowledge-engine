"""Provenance tracking for Step 8 auto-discovered documents -- every
document this pipeline ever fetches gets a row here (doc_id,
source_query, source_url, discovered_at), which is how a document is
"visibly distinct" from a P6-allowlisted one: P6 documents have no row
in this table at all; a lookup miss IS the signal a document is NOT
auto-discovered.

Also holds `invocations` -- a log of every call to
`discovery.pipeline.run_discovery()`, regardless of caller, added
2026-09-06 after a real incident: a direct call fired for query "alpha
apples" with no corresponding /search API call, no query_log.db entry,
and no explanation found after checking cron, other users' sessions, the
systemd journal, and every running process (see
LOGBOOK_09062026_*.md for the full investigation -- inconclusive on WHO
called it, but conclusive that NOTHING was logging the call itself).
`run_discovery()` now logs an `invocations` row as its very first action,
before anything else can fail or be interrupted, specifically so this
kind of untraceable call can never happen silently again.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ProvenanceRecord:
    doc_id: str
    source_query: str
    source_url: str
    discovered_at: str


@dataclass
class InvocationRecord:
    invocation_id: int
    query: str
    caller: str
    pid: int
    argv: str
    timestamp: str


class ProvenanceStore:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS provenance (
                doc_id TEXT PRIMARY KEY,
                source_query TEXT NOT NULL,
                source_url TEXT NOT NULL,
                discovered_at TEXT NOT NULL
            )"""
        )
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS invocations (
                invocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                caller TEXT NOT NULL,
                pid INTEGER NOT NULL,
                argv TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )"""
        )
        self._conn.commit()

    def record(self, doc_id: str, source_query: str, source_url: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO provenance (doc_id, source_query, source_url, discovered_at) VALUES (?, ?, ?, ?)",
            (doc_id, source_query, source_url, datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()

    def get(self, doc_id: str) -> ProvenanceRecord | None:
        row = self._conn.execute(
            "SELECT doc_id, source_query, source_url, discovered_at FROM provenance WHERE doc_id = ?", (doc_id,)
        ).fetchone()
        return ProvenanceRecord(*row) if row else None

    def all_records(self) -> list[ProvenanceRecord]:
        rows = self._conn.execute("SELECT doc_id, source_query, source_url, discovered_at FROM provenance").fetchall()
        return [ProvenanceRecord(*r) for r in rows]

    def log_invocation(self, query: str, caller: str = "unknown") -> int:
        """Records that run_discovery() was called, independent of whether
        it was reached via the /search API or any other path. Called as
        the FIRST line of run_discovery(), before web_search/robots/fetch
        -- so even a call that crashes immediately after still leaves a
        row here."""
        argv = " ".join(sys.argv)
        cur = self._conn.execute(
            "INSERT INTO invocations (query, caller, pid, argv, timestamp) VALUES (?, ?, ?, ?, ?)",
            (query, caller, os.getpid(), argv, datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()
        return cur.lastrowid

    def all_invocations(self) -> list[InvocationRecord]:
        rows = self._conn.execute(
            "SELECT invocation_id, query, caller, pid, argv, timestamp FROM invocations ORDER BY invocation_id"
        ).fetchall()
        return [InvocationRecord(*r) for r in rows]

    def close(self) -> None:
        self._conn.close()
