import pytest

from access.acl_store import AclStore
from access.git_connector import ingest_git_repo
from config import get_settings

pytestmark = pytest.mark.requires_postgres


@pytest.fixture()
def store():
    s = AclStore(get_settings().postgres_dsn)
    s.clear()
    yield s
    s.clear()
    s.close()


def _make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "public.txt").write_text("a public file about apples", encoding="utf-8")
    (repo / "private.txt").write_text("a private file about pears", encoding="utf-8")
    (repo / "unmanifested.txt").write_text("a file nobody described in the manifest", encoding="utf-8")
    return repo


def test_manifested_files_get_correct_acl(tmp_path, store):
    repo = _make_repo(tmp_path)
    manifest = {
        "public.txt": {"public": True},
        "private.txt": {"owner": "alice"},
    }
    ingest_git_repo(repo, manifest, tmp_path / "index", tmp_path / "registry.db", store)

    assert store.is_authorized("anyone", "public") is True
    assert store.is_authorized("bob", "private") is False
    assert store.is_authorized("alice", "private") is True


def test_unmanifested_file_defaults_to_locked_down(tmp_path, store):
    repo = _make_repo(tmp_path)
    report = ingest_git_repo(repo, {}, tmp_path / "index", tmp_path / "registry.db", store)

    assert "unmanifested.txt" in report.unmanifested_locked_down
    assert store.is_authorized("anyone", "unmanifested") is False
    assert store.is_authorized("alice", "unmanifested") is False


def test_report_counts_match_files_processed(tmp_path, store):
    repo = _make_repo(tmp_path)
    report = ingest_git_repo(repo, {}, tmp_path / "index", tmp_path / "registry.db", store)
    assert report.documents_ingested == 3
    assert report.documents_registered == 3


def test_manifest_file_itself_is_excluded_from_acl_registration(tmp_path, store):
    # caught by running this for real against data/enterprise_demo/: a JSON
    # manifest sitting inside the same directory it describes otherwise gets
    # scanned and registered as if it were regular content
    repo = _make_repo(tmp_path)
    manifest_path = repo / "acl_manifest.json"
    manifest_path.write_text('{"public.txt": {"public": true}}', encoding="utf-8")

    report = ingest_git_repo(
        repo, {"public.txt": {"public": True}}, tmp_path / "index", tmp_path / "registry.db", store,
        manifest_path=manifest_path,
    )

    assert "acl_manifest" not in report.unmanifested_locked_down
    assert report.documents_registered == 3  # public.txt, private.txt, unmanifested.txt -- not the manifest itself
