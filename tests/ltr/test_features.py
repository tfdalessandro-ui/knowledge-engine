from datetime import datetime, timedelta, timezone

from ltr.features import FEATURE_NAMES, SOURCE_TYPE_VOCAB, row_to_features, rows_to_dataset


def _row(**overrides):
    base = {
        "query_id": 1, "doc_id": "d1", "chunk_id": "d1::0", "rank": 0,
        "bm25_score": 2.5, "vector_score": 0.8, "rrf_score": 0.05,
        "source_type": "txt", "ingested_at": None, "label": 1,
    }
    base.update(overrides)
    return base


def test_row_to_features_length_matches_feature_names():
    features = row_to_features(_row())
    assert len(features) == len(FEATURE_NAMES)


def test_none_scores_become_zero():
    features = row_to_features(_row(bm25_score=None, vector_score=None))
    assert features[FEATURE_NAMES.index("bm25_score")] == 0.0
    assert features[FEATURE_NAMES.index("vector_score")] == 0.0


def test_missing_ingested_at_yields_sentinel_recency():
    features = row_to_features(_row(ingested_at=None))
    assert features[FEATURE_NAMES.index("recency_days")] == -1.0


def test_recency_computed_correctly():
    now = datetime.now(timezone.utc)
    ingested = now - timedelta(days=3)
    features = row_to_features(_row(ingested_at=ingested.isoformat()), now=now)
    recency = features[FEATURE_NAMES.index("recency_days")]
    assert 2.9 < recency < 3.1


def test_known_source_type_maps_to_vocab_code():
    features = row_to_features(_row(source_type="pdf"))
    assert features[FEATURE_NAMES.index("source_type_code")] == SOURCE_TYPE_VOCAB["pdf"]


def test_unknown_source_type_gets_sentinel_code():
    features = row_to_features(_row(source_type="exe"))
    assert features[FEATURE_NAMES.index("source_type_code")] == -1


def test_rows_to_dataset_group_sizes_match_query_boundaries():
    rows = [
        _row(query_id=1, doc_id="a"), _row(query_id=1, doc_id="b"), _row(query_id=1, doc_id="c"),
        _row(query_id=2, doc_id="d"), _row(query_id=2, doc_id="e"),
    ]
    X, y, group = rows_to_dataset(rows)
    assert X.shape == (5, len(FEATURE_NAMES))
    assert list(y) == [1, 1, 1, 1, 1]
    assert group == [3, 2]
