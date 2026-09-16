"""Candidate registry for the research-to-production loop -- versions and
tracks each technique tried, its P0-harness benchmark, and its mechanical
promote/drop/rollback lifecycle. Single-process CLI usage only (the daily
`research/loop.py` driver), no concurrent-thread access like
`ltr/query_log.py` has to handle for the live API, so no threading lock
needed here.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

DECISION_DELAY_DAYS = 14
ROLLING_WINDOW_SIZE = 5


@dataclass
class Candidate:
    candidate_id: int
    name: str
    source: str
    description: str
    config_diff: str  # JSON-serialized dict of the actual parameter/code change
    benchmark_before: float
    benchmark_after: float
    created_at: str
    decision_date: str
    status: str  # 'pending' | 'promoted' | 'dropped' | 'rolled_back'
    promoted_at: str | None


class CandidateStore:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS candidates (
                candidate_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                source TEXT NOT NULL,
                description TEXT NOT NULL,
                config_diff TEXT NOT NULL,
                benchmark_before REAL NOT NULL,
                benchmark_after REAL NOT NULL,
                created_at TEXT NOT NULL,
                decision_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                promoted_at TEXT
            )"""
        )
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS version_history (
                version_id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER,
                ndcg_score REAL NOT NULL,
                recorded_at TEXT NOT NULL
            )"""
        )
        self._conn.commit()

    def register(self, name: str, source: str, description: str, config_diff: str,
                 benchmark_before: float, benchmark_after: float) -> int:
        now = datetime.now(timezone.utc)
        decision_date = now + timedelta(days=DECISION_DELAY_DAYS)
        cur = self._conn.execute(
            "INSERT INTO candidates (name, source, description, config_diff, benchmark_before, "
            "benchmark_after, created_at, decision_date, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')",
            (name, source, description, config_diff, benchmark_before, benchmark_after,
             now.isoformat(), decision_date.isoformat()),
        )
        self._conn.commit()
        return cur.lastrowid

    def pending_past_decision_date(self) -> list[Candidate]:
        now = datetime.now(timezone.utc).isoformat()
        rows = self._conn.execute(
            "SELECT * FROM candidates WHERE status = 'pending' AND decision_date <= ?", (now,)
        ).fetchall()
        return [Candidate(*r) for r in rows]

    def set_status(self, candidate_id: int, status: str, promoted_at: str | None = None) -> None:
        self._conn.execute(
            "UPDATE candidates SET status = ?, promoted_at = ? WHERE candidate_id = ?",
            (status, promoted_at, candidate_id),
        )
        self._conn.commit()

    def record_version_score(self, candidate_id: int | None, ndcg_score: float) -> None:
        self._conn.execute(
            "INSERT INTO version_history (candidate_id, ndcg_score, recorded_at) VALUES (?, ?, ?)",
            (candidate_id, ndcg_score, datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()

    def trailing_window(self, n: int = ROLLING_WINDOW_SIZE) -> list[float]:
        rows = self._conn.execute(
            "SELECT ndcg_score FROM version_history ORDER BY version_id DESC LIMIT ?", (n,)
        ).fetchall()
        return [r[0] for r in rows]

    def all_candidates(self) -> list[Candidate]:
        rows = self._conn.execute("SELECT * FROM candidates ORDER BY candidate_id").fetchall()
        return [Candidate(*r) for r in rows]

    def close(self) -> None:
        self._conn.close()
