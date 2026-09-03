"""Document access-control storage, backed by PostgreSQL (the P5 tech
choice, replacing SQLite "at this scale" per the roadmap -- this is a new,
dedicated store for the ACL model P5 introduces, not a migration of every
prior phase's SQLite store, which isn't what P5's exit criterion needs).

Authorization model, deliberately simple for a v1 gate: a document is
visible to a user if it's public, OR the user owns it, OR the user has an
explicit grant. No groups/roles yet -- the exit criterion is proving
cross-user leakage is impossible, not modeling a full enterprise permission
system.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass

import psycopg


@dataclass
class DocumentAccess:
    doc_id: str
    source: str
    owner_user_id: str | None
    is_public: bool


class AclStore:
    def __init__(self, dsn: str):
        self._lock = threading.Lock()  # psycopg connections aren't safe for concurrent multi-thread use either
        self._conn = psycopg.connect(dsn, autocommit=False)
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    owner_user_id TEXT,
                    is_public BOOLEAN NOT NULL DEFAULT FALSE
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS document_acl (
                    doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
                    user_id TEXT NOT NULL,
                    PRIMARY KEY (doc_id, user_id)
                )
                """
            )
            self._conn.commit()

    def register_document(self, doc_id: str, source: str, owner_user_id: str | None = None, is_public: bool = False) -> None:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (doc_id, source, owner_user_id, is_public)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (doc_id) DO UPDATE SET
                    source = excluded.source, owner_user_id = excluded.owner_user_id, is_public = excluded.is_public
                """,
                (doc_id, source, owner_user_id, is_public),
            )
            self._conn.commit()

    def grant(self, doc_id: str, user_id: str) -> None:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO document_acl (doc_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (doc_id, user_id),
            )
            self._conn.commit()

    def revoke(self, doc_id: str, user_id: str) -> None:
        with self._lock, self._conn.cursor() as cur:
            cur.execute("DELETE FROM document_acl WHERE doc_id = %s AND user_id = %s", (doc_id, user_id))
            self._conn.commit()

    def is_authorized(self, user_id: str, doc_id: str) -> bool:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM documents d
                WHERE d.doc_id = %s AND (
                    d.is_public
                    OR d.owner_user_id = %s
                    OR EXISTS (SELECT 1 FROM document_acl a WHERE a.doc_id = d.doc_id AND a.user_id = %s)
                )
                """,
                (doc_id, user_id, user_id),
            )
            return cur.fetchone() is not None

    def authorized_doc_ids(self, user_id: str) -> set[str]:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT d.doc_id FROM documents d
                LEFT JOIN document_acl a ON a.doc_id = d.doc_id AND a.user_id = %s
                WHERE d.is_public OR d.owner_user_id = %s OR a.user_id IS NOT NULL
                """,
                (user_id, user_id),
            )
            return {row[0] for row in cur.fetchall()}

    def get_document(self, doc_id: str) -> DocumentAccess | None:
        with self._lock, self._conn.cursor() as cur:
            cur.execute("SELECT doc_id, source, owner_user_id, is_public FROM documents WHERE doc_id = %s", (doc_id,))
            row = cur.fetchone()
            return DocumentAccess(*row) if row else None

    def clear(self) -> None:
        """Wipes both tables -- used by tests, not exposed via CLI."""
        with self._lock, self._conn.cursor() as cur:
            cur.execute("TRUNCATE document_acl, documents CASCADE")
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "AclStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
