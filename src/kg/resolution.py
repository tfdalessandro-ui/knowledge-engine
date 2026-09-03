"""Entity resolution: exact match auto-resolves to a canonical entity;
near-duplicate (fuzzy) matches are queued for manual review, never
auto-merged -- per the P4 spec ("exact+fuzzy entity resolution with a
manual merge-review queue"). Auto-merging fuzzy matches would silently
conflate distinct entities (e.g. two similarly-named but different
products); a review queue keeps that judgment call with a human.
"""
from __future__ import annotations

import re
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from rapidfuzz import fuzz

FUZZY_THRESHOLD = 85  # token_sort_ratio; below this, not even queued for review


def normalize(text: str) -> str:
    """Canonicalization key: lowercase, punctuation stripped, whitespace
    collapsed -- so "BM25", "bm25", and "BM-25" all resolve to the same
    exact-match bucket."""
    cleaned = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return re.sub(r"\s+", " ", cleaned)


def canonical_id(text: str, label: str) -> str:
    return f"{label}:{normalize(text)}"


@dataclass
class MergeCandidate:
    candidate_id: int
    entity_a: str
    entity_b: str
    label: str
    score: float
    status: str  # "pending" | "merged" | "rejected"


class MergeReviewQueue:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS merge_candidates (
                candidate_id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_a TEXT NOT NULL,
                entity_b TEXT NOT NULL,
                label TEXT NOT NULL,
                score REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                UNIQUE(entity_a, entity_b, label)
            )
            """
        )
        self._conn.commit()

    def add_candidate(self, entity_a: str, entity_b: str, label: str, score: float) -> None:
        a, b = sorted([entity_a, entity_b])  # order-independent dedup
        with self._lock:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO merge_candidates (entity_a, entity_b, label, score, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (a, b, label, score, datetime.now(timezone.utc).isoformat()),
            )
            self._conn.commit()

    def list_pending(self) -> list[MergeCandidate]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT candidate_id, entity_a, entity_b, label, score, status "
                "FROM merge_candidates WHERE status = 'pending'"
            ).fetchall()
            return [MergeCandidate(*r) for r in rows]

    def resolve(self, candidate_id: int, merge: bool) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE merge_candidates SET status = ? WHERE candidate_id = ?",
                ("merged" if merge else "rejected", candidate_id),
            )
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "MergeReviewQueue":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


class EntityResolver:
    """Tracks canonical entities seen so far (per label) within a single KG
    extraction run, and flags near-duplicates for review instead of
    silently merging them."""

    def __init__(self, review_queue: MergeReviewQueue):
        self._review_queue = review_queue
        self._known: dict[str, dict[str, str]] = {}  # label -> {canonical_id: display_name}

    def resolve(self, text: str, label: str) -> str:
        cid = canonical_id(text, label)
        bucket = self._known.setdefault(label, {})

        if cid in bucket:
            return cid  # exact match (post-normalization) -- auto-resolved

        for existing_cid, existing_name in bucket.items():
            score = fuzz.token_sort_ratio(normalize(text), normalize(existing_name))
            if score >= FUZZY_THRESHOLD:
                self._review_queue.add_candidate(text, existing_name, label, score)
                # NOT merged automatically -- keep as its own entity until a human approves the merge

        bucket[cid] = text
        return cid
