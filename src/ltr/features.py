"""Turns logged query-candidate rows (query_log.QueryLog.training_rows())
into a LightGBM LambdaMART-ready (X, y, group) dataset -- the exact feature
set the roadmap specifies: BM25 score, vector score, recency, source type.
(RRF score is included too, as a free extra signal already computed at
query time.)
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

FEATURE_NAMES = ["bm25_score", "vector_score", "rrf_score", "recency_days", "source_type_code"]

# Fixed small vocabulary -- the P1 parser formats, plus a fallback for
# anything else. A numeric code, not one-hot: with this few categories and a
# tree-based model, LightGBM can still split on it usefully, and it keeps
# the feature vector fixed-width without a separate encoder to persist.
SOURCE_TYPE_VOCAB = {"txt": 0, "md": 1, "html": 2, "csv": 3, "json": 4, "xml": 5,
                      "docx": 6, "xlsx": 7, "pptx": 8, "pdf": 9}
UNKNOWN_SOURCE_TYPE_CODE = -1


def _recency_days(ingested_at: str | None, now: datetime) -> float:
    if not ingested_at:
        return -1.0  # unknown recency -- distinguishable from "just ingested" (0.0)
    try:
        ingested = datetime.fromisoformat(ingested_at)
    except ValueError:
        return -1.0
    return (now - ingested).total_seconds() / 86400


def row_to_features(row: dict, now: datetime | None = None) -> list[float]:
    now = now or datetime.now(timezone.utc)
    return [
        row["bm25_score"] if row["bm25_score"] is not None else 0.0,
        row["vector_score"] if row["vector_score"] is not None else 0.0,
        row["rrf_score"] if row["rrf_score"] is not None else 0.0,
        _recency_days(row["ingested_at"], now),
        SOURCE_TYPE_VOCAB.get(row["source_type"], UNKNOWN_SOURCE_TYPE_CODE),
    ]


def rows_to_dataset(rows: list[dict]) -> tuple[np.ndarray, np.ndarray, list[int]]:
    """rows must already be grouped by query_id in contiguous runs (which is
    exactly what QueryLog.training_rows() produces) -- LightGBM's ranking
    objective needs a `group` array of per-query candidate counts lined up
    with contiguous rows, not a query_id column."""
    now = datetime.now(timezone.utc)
    X = np.array([row_to_features(r, now) for r in rows], dtype="float64")
    y = np.array([r["label"] for r in rows], dtype="int32")

    group: list[int] = []
    current_query_id = None
    for r in rows:
        if r["query_id"] != current_query_id:
            group.append(0)
            current_query_id = r["query_id"]
        group[-1] += 1

    return X, y, group
