"""P5 exit criterion, made concrete: a permission-denial test suite proving
user A cannot see user B's private files in results. Runs the real Git
connector over the real data/enterprise_demo/ corpus (mixed public/private/
shared documents, ACL manifest included in the repo -- not synthetic
throwaway data) into a real Tantivy index + real PostgreSQL ACL store, then
exercises permission-aware search as different users.
"""
from pathlib import Path

import pytest

from access.acl_store import AclStore
from access.git_connector import ingest_git_repo
from access.permission_filter import PermissionAwareSearch
from config import get_settings
from eval.real_index import RealBM25Index

pytestmark = pytest.mark.requires_postgres

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = REPO_ROOT / "data" / "enterprise_demo"


@pytest.fixture(scope="module")
def permission_search(tmp_path_factory):
    import json

    tmp_dir = tmp_path_factory.mktemp("enterprise_demo_index")
    manifest = json.loads((DEMO_DIR / "acl_manifest.json").read_text(encoding="utf-8"))

    store = AclStore(get_settings().postgres_dsn)
    store.clear()
    ingest_git_repo(
        DEMO_DIR, manifest, tmp_dir / "index", tmp_dir / "registry.db", store,
        manifest_path=DEMO_DIR / "acl_manifest.json",
    )

    index = RealBM25Index(tmp_dir / "index")
    yield PermissionAwareSearch(index, store)
    store.clear()
    store.close()


def test_bob_cannot_see_alice_private_document(permission_search):
    # "Nightingale" only appears in alice_private_notes.txt
    results = permission_search.search("bob", "Nightingale", k=10)
    assert "alice_private_notes" not in results


def test_alice_cannot_see_bob_private_document(permission_search):
    # "Kingfisher" only appears in bob_private_notes.txt
    results = permission_search.search("alice", "Kingfisher", k=10)
    assert "bob_private_notes" not in results


def test_unrelated_third_user_sees_neither_private_document(permission_search):
    results_a = permission_search.search("carol", "Nightingale", k=10)
    results_b = permission_search.search("carol", "Kingfisher", k=10)
    assert "alice_private_notes" not in results_a
    assert "bob_private_notes" not in results_b


def test_public_document_is_visible_to_everyone(permission_search):
    for user in ("alice", "bob", "carol"):
        results = permission_search.search(user, "remote-work policy", k=10)
        assert "public_policy" in results


def test_explicitly_shared_document_is_visible_to_the_grantee(permission_search):
    # shared_project_plan.txt is owned by alice, granted to bob
    results = permission_search.search("bob", "Project Falcon", k=10)
    assert "shared_project_plan" in results


def test_shared_document_is_not_visible_to_a_non_grantee(permission_search):
    results = permission_search.search("carol", "Project Falcon", k=10)
    assert "shared_project_plan" not in results


def test_owner_can_always_see_their_own_document(permission_search):
    results = permission_search.search("alice", "Nightingale", k=10)
    assert "alice_private_notes" in results
