"""End-to-end test of the /search + /select wiring: builds a real small
index, points the API module's settings at it directly (bypassing env vars
for test isolation), and verifies a search logs a query with candidate
features, and a selection is recorded against it."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api.main as api_main
from config import Settings
from ingest.pipeline import run_ingest


def _make_corpus(tmp_path: Path) -> Path:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "alpha.txt").write_text("alpha document about apples and orchards", encoding="utf-8")
    (corpus / "beta.txt").write_text("beta document about bicycles and gears", encoding="utf-8")
    return corpus


@pytest.fixture()
def client(tmp_path):
    corpus = _make_corpus(tmp_path)
    tantivy_dir = tmp_path / "index"
    registry_db = tmp_path / "registry.db"
    faiss_path = tmp_path / "vectors" / "index.faiss"
    vector_registry_db = tmp_path / "vectors.db"

    run_ingest(corpus, tantivy_dir, registry_db, vector_index_path=faiss_path, vector_registry_db=vector_registry_db)

    api_main._settings = Settings(
        tantivy_index_dir=tantivy_dir,
        registry_db_path=registry_db,
        faiss_index_path=faiss_path,
        vector_registry_db_path=vector_registry_db,
        query_log_db_path=tmp_path / "query_log.db",
        # discovery_enabled=False disables Step 8's sparse-result trigger
        # entirely for this test client -- found live 2026-09-06 that
        # leaving it enabled let this fixture's tiny 2-document test
        # corpus produce low BM25 scores (a small corpus legitimately
        # scores lower than the real 47-doc one MIN_MEANINGFUL_BM25_SCORE
        # was calibrated against), which falsely tripped is_sparse() and
        # fired REAL, live web fetches against the real SearXNG/internet
        # on every test run -- a real test-isolation bug, not a
        # hypothetical one (see LOGBOOK_09062026_*.md for the incident
        # this caused). Discovery has its own dedicated, fully-isolated
        # tests in tests/discovery/ -- this suite tests /search's core
        # behavior and should never reach the network.
        discovery_enabled=False,
    )
    api_main._index = None
    api_main._query_log = None
    api_main._registry = None

    return TestClient(api_main.app)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_search_returns_query_id_and_hits(client):
    resp = client.get("/search", params={"q": "alpha apples", "k": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert body["query_id"] > 0
    assert len(body["hits"]) > 0
    assert body["hits"][0]["doc_id"] == "alpha"


def test_search_logs_a_query(client):
    client.get("/search", params={"q": "alpha apples", "k": 5})
    from ltr.query_log import QueryLog

    with QueryLog(api_main._settings.query_log_db_path) as log:
        assert log.count_queries() == 1


def test_select_records_an_interaction(client):
    search_resp = client.get("/search", params={"q": "alpha apples", "k": 5})
    query_id = search_resp.json()["query_id"]
    doc_id = search_resp.json()["hits"][0]["doc_id"]

    select_resp = client.post("/select", json={"query_id": query_id, "doc_id": doc_id, "rank": 0})
    assert select_resp.status_code == 200

    from ltr.query_log import QueryLog

    with QueryLog(api_main._settings.query_log_db_path) as log:
        assert log.count_interactions() == 1


def test_select_rejects_invalid_query_id(client):
    resp = client.post("/select", json={"query_id": 0, "doc_id": "alpha"})
    assert resp.status_code == 400


def test_discovery_never_fires_from_this_test_suite(client):
    """Regression test for the 2026-09-06 incident: this suite's tiny
    2-doc corpus can legitimately produce low BM25 scores that would
    trip is_sparse() against the real MIN_MEANINGFUL_BM25_SCORE, firing
    REAL web fetches as a side effect of running tests. Confirms
    discovery_enabled=False (set in the `client` fixture above) actually
    prevents that -- checked by asserting the response never reports
    discovery_triggered=True, for the fixture's own on-topic query AND a
    deliberately unrelated one that would be a much stronger sparse
    candidate than "alpha apples" ever was."""
    for q in ["alpha apples", "a query with zero relation to this tiny test corpus whatsoever"]:
        resp = client.get("/search", params={"q": q, "k": 5})
        assert resp.json()["discovery_triggered"] is False, f"discovery fired for {q!r} despite discovery_enabled=False"
