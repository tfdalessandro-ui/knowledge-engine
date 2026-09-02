from ltr.query_log import CandidateRecord, QueryLog


def _candidates():
    return [
        CandidateRecord("doc1", "doc1::0", 0, 3.0, 0.9, 0.05, "txt", "2026-01-01T00:00:00+00:00"),
        CandidateRecord("doc2", "doc2::0", 1, 2.0, 0.7, 0.03, "md", "2026-01-02T00:00:00+00:00"),
    ]


def test_log_query_returns_id_and_persists_candidates(tmp_path):
    log = QueryLog(tmp_path / "log.db")
    query_id = log.log_query("test query", "hybrid", _candidates())
    assert query_id > 0
    assert log.count_queries() == 1


def test_log_selection_and_count_interactions(tmp_path):
    log = QueryLog(tmp_path / "log.db")
    query_id = log.log_query("test query", "hybrid", _candidates())
    assert log.count_interactions() == 0
    log.log_selection(query_id, "doc1", "doc1::0", 0)
    assert log.count_interactions() == 1


def test_training_rows_labels_selected_candidate_positive(tmp_path):
    log = QueryLog(tmp_path / "log.db")
    query_id = log.log_query("test query", "hybrid", _candidates())
    log.log_selection(query_id, "doc2", "doc2::0", 1)

    rows = log.training_rows()
    labels = {r["doc_id"]: r["label"] for r in rows}
    assert labels == {"doc1": 0, "doc2": 1}


def test_training_rows_excludes_queries_with_no_selection(tmp_path):
    log = QueryLog(tmp_path / "log.db")
    log.log_query("unselected query", "hybrid", _candidates())  # no selection logged
    query_id_2 = log.log_query("selected query", "hybrid", _candidates())
    log.log_selection(query_id_2, "doc1", "doc1::0", 0)

    rows = log.training_rows()
    query_ids = {r["query_id"] for r in rows}
    assert query_ids == {query_id_2}


def test_training_rows_grouped_contiguously_by_query(tmp_path):
    log = QueryLog(tmp_path / "log.db")
    for i in range(3):
        qid = log.log_query(f"query {i}", "hybrid", _candidates())
        log.log_selection(qid, "doc1", "doc1::0", 0)

    rows = log.training_rows()
    seen = []
    for r in rows:
        if not seen or seen[-1] != r["query_id"]:
            seen.append(r["query_id"])
    assert len(seen) == 3  # each query_id appears as one contiguous run, not interleaved
