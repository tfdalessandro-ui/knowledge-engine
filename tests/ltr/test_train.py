"""Proves the LightGBM plumbing works mechanically against synthetic data
with a deliberately lowered threshold -- NOT a claim that the P3 exit
criterion is met. This repo's real query log is empty (no live usage), so
`train_reranker` is expected to stay BLOCKED at the real config threshold;
that's the default/production behavior this test also checks."""
from ltr.query_log import CandidateRecord, QueryLog
from ltr.train import train_reranker


def _seed_synthetic_interactions(db_path, n_queries: int) -> None:
    log = QueryLog(db_path)
    for i in range(n_queries):
        candidates = [
            CandidateRecord(f"doc{i}_good", f"doc{i}_good::0", 0, 5.0, 0.9, 0.05, "txt", None),
            CandidateRecord(f"doc{i}_bad", f"doc{i}_bad::0", 1, 1.0, 0.2, 0.02, "txt", None),
        ]
        query_id = log.log_query(f"query {i}", "hybrid", candidates)
        log.log_selection(query_id, f"doc{i}_good", f"doc{i}_good::0", 0)
    log.close()


def test_blocked_at_real_config_threshold_with_empty_log(tmp_path):
    db_path = tmp_path / "log.db"
    QueryLog(db_path).close()  # creates empty tables, no interactions
    result = train_reranker(db_path, min_interactions=500, model_out_path=tmp_path / "model.txt")
    assert result.trained is False
    assert result.interactions == 0
    assert "blocked" in result.reason.lower()


def test_blocked_below_a_lowered_threshold(tmp_path):
    db_path = tmp_path / "log.db"
    _seed_synthetic_interactions(db_path, n_queries=3)
    result = train_reranker(db_path, min_interactions=10, model_out_path=tmp_path / "model.txt")
    assert result.trained is False
    assert result.interactions == 3


def test_trains_once_synthetic_data_clears_a_lowered_threshold(tmp_path):
    db_path = tmp_path / "log.db"
    _seed_synthetic_interactions(db_path, n_queries=20)
    model_path = tmp_path / "model.txt"
    result = train_reranker(db_path, min_interactions=10, model_out_path=model_path)

    assert result.trained is True
    assert result.interactions == 20
    assert model_path.exists()
    assert model_path.stat().st_size > 0
