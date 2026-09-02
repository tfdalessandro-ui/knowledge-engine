from ltr.query_log import CandidateRecord, QueryLog
from ltr.rerank import load_model, rerank
from ltr.train import train_reranker


def _seed(db_path, n_queries: int) -> None:
    log = QueryLog(db_path)
    for i in range(n_queries):
        candidates = [
            CandidateRecord(f"doc{i}_good", f"doc{i}_good::0", 0, 5.0, 0.9, 0.05, "txt", None),
            CandidateRecord(f"doc{i}_bad", f"doc{i}_bad::0", 1, 1.0, 0.2, 0.02, "txt", None),
        ]
        query_id = log.log_query(f"query {i}", "hybrid", candidates)
        log.log_selection(query_id, f"doc{i}_good", f"doc{i}_good::0", 0)
    log.close()


def test_rerank_reorders_by_predicted_relevance(tmp_path):
    db_path = tmp_path / "log.db"
    _seed(db_path, n_queries=20)
    model_path = tmp_path / "model.txt"
    train_reranker(db_path, min_interactions=10, model_out_path=model_path)

    model = load_model(model_path)
    # a low-signal candidate first, a high-signal one second -- rerank should flip them
    rows = [
        {"bm25_score": 1.0, "vector_score": 0.2, "rrf_score": 0.02, "ingested_at": None, "source_type": "txt"},
        {"bm25_score": 5.0, "vector_score": 0.9, "rrf_score": 0.05, "ingested_at": None, "source_type": "txt"},
    ]
    reordered = rerank(model, rows)
    assert len(reordered) == 2
    assert reordered[0]["bm25_score"] == 5.0  # the strong-signal row should rank first


def test_rerank_empty_input():
    assert rerank(None, []) == []
