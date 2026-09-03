import pytest

from access.acl_store import AclStore
from access.permission_filter import PermissionAwareSearch
from config import get_settings

pytestmark = pytest.mark.requires_postgres


class _FakeIndex:
    """Returns a fixed ranking regardless of query -- isolates
    PermissionAwareSearch's filtering logic from real BM25 behavior."""

    def __init__(self, ranking):
        self._ranking = ranking

    def search(self, query, k):
        return self._ranking[:k]


@pytest.fixture()
def store():
    s = AclStore(get_settings().postgres_dsn)
    s.clear()
    yield s
    s.clear()
    s.close()


def test_unauthorized_candidates_are_filtered_out(store):
    store.register_document("public_doc", "git", is_public=True)
    store.register_document("private_doc", "git", owner_user_id="alice")
    index = _FakeIndex(["private_doc", "public_doc"])
    search = PermissionAwareSearch(index, store)

    results = search.search("bob", "anything", k=10)
    assert results == ["public_doc"]


def test_result_order_is_preserved_after_filtering(store):
    for doc_id in ("a", "b", "c"):
        store.register_document(doc_id, "git", is_public=True)
    index = _FakeIndex(["c", "a", "b"])
    search = PermissionAwareSearch(index, store)

    assert search.search("anyone", "q", k=10) == ["c", "a", "b"]


def test_truncates_to_k_after_filtering(store):
    for doc_id in ("a", "b", "c", "d"):
        store.register_document(doc_id, "git", is_public=True)
    index = _FakeIndex(["a", "b", "c", "d"])
    search = PermissionAwareSearch(index, store)

    assert search.search("anyone", "q", k=2) == ["a", "b"]
