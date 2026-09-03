"""Permission-aware search: wraps any existing index (RealBM25Index,
HybridIndex -- anything with `search(query, k) -> list[doc_id]`) and
filters results by the requesting user's access before the final ranked
list is returned, per the P5 spec ("retrieval filters by the requesting
user's permissions before ranking").

Implementation note on "before ranking": this over-fetches a larger
candidate pool from the underlying index, filters it by ACL, then truncates
to `k` -- not a true index-level ACL push-down (which would need
per-user-filtered Tantivy/FAISS queries, out of scope for this gate). The
practical effect is the same for the exit criterion that matters (a
disallowed document never appears in the final results), with one known
limitation: if a user's authorized set is a small fraction of a large
corpus, the fixed fanout might return fewer than `k` results even though
more authorized matches exist further down the underlying ranking.
"""
from __future__ import annotations

from typing import Protocol

from access.acl_store import AclStore


class SearchableIndex(Protocol):
    def search(self, query: str, k: int) -> list[str]: ...


class PermissionAwareSearch:
    def __init__(self, index: SearchableIndex, acl_store: AclStore, fanout_multiplier: int = 5):
        self._index = index
        self._acl_store = acl_store
        self._fanout_multiplier = fanout_multiplier

    def search(self, user_id: str, query: str, k: int) -> list[str]:
        authorized = self._acl_store.authorized_doc_ids(user_id)
        candidates = self._index.search(query, k * self._fanout_multiplier)
        return [doc_id for doc_id in candidates if doc_id in authorized][:k]
