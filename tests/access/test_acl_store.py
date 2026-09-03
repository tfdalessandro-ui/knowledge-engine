import pytest

from access.acl_store import AclStore
from config import get_settings

pytestmark = pytest.mark.requires_postgres


@pytest.fixture()
def store():
    s = AclStore(get_settings().postgres_dsn)
    s.clear()
    yield s
    s.clear()
    s.close()


def test_public_document_is_authorized_for_anyone(store):
    store.register_document("doc1", "git", is_public=True)
    assert store.is_authorized("anyone", "doc1") is True


def test_private_document_denies_non_owner(store):
    store.register_document("doc1", "git", owner_user_id="alice")
    assert store.is_authorized("alice", "doc1") is True
    assert store.is_authorized("bob", "doc1") is False


def test_explicit_grant_authorizes_a_non_owner(store):
    store.register_document("doc1", "git", owner_user_id="alice")
    store.grant("doc1", "bob")
    assert store.is_authorized("bob", "doc1") is True


def test_revoke_removes_access(store):
    store.register_document("doc1", "git", owner_user_id="alice")
    store.grant("doc1", "bob")
    store.revoke("doc1", "bob")
    assert store.is_authorized("bob", "doc1") is False


def test_unknown_document_is_not_authorized(store):
    assert store.is_authorized("alice", "nonexistent") is False


def test_authorized_doc_ids_combines_public_owned_and_granted(store):
    store.register_document("public_doc", "git", is_public=True)
    store.register_document("alice_doc", "git", owner_user_id="alice")
    store.register_document("bob_doc", "git", owner_user_id="bob")
    store.register_document("shared_doc", "git", owner_user_id="bob")
    store.grant("shared_doc", "alice")

    assert store.authorized_doc_ids("alice") == {"public_doc", "alice_doc", "shared_doc"}


def test_authorized_doc_ids_never_includes_other_users_private_docs(store):
    store.register_document("alice_doc", "git", owner_user_id="alice")
    store.register_document("bob_doc", "git", owner_user_id="bob")
    assert "bob_doc" not in store.authorized_doc_ids("alice")
    assert "alice_doc" not in store.authorized_doc_ids("bob")
