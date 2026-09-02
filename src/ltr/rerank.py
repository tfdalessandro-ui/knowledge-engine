"""Applies a trained LTR model to reorder a list of candidates. Only
meaningful once `ltr.train` has actually produced a model (see its module
docstring for why that hasn't happened with real data yet)."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from ltr.features import row_to_features


def load_model(model_path: Path):
    import lightgbm as lgb

    return lgb.Booster(model_file=str(model_path))


def rerank(model, rows: Sequence[dict]) -> list[dict]:
    """rows: candidate dicts with the same keys as query_log's
    training_rows() (bm25_score/vector_score/rrf_score/ingested_at/
    source_type). Returns the same rows, reordered by predicted relevance,
    most relevant first."""
    if not rows:
        return []
    X = [row_to_features(r) for r in rows]
    scores = model.predict(X)
    order = sorted(range(len(rows)), key=lambda i: -scores[i])
    return [rows[i] for i in order]
