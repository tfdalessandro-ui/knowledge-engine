"""Reciprocal Rank Fusion: combine several ranked lists of doc_ids into one,
without needing the source rankers' scores to be on comparable scales (BM25
and cosine similarity are not)."""
from __future__ import annotations

from typing import Sequence


def rrf_scores(rankings: Sequence[Sequence[str]], k: int = 60) -> tuple[dict[str, float], dict[str, int]]:
    """Returns (score per doc_id, first-seen order per doc_id) -- the shared
    core both `reciprocal_rank_fusion` (ordering only) and callers that also
    want the numeric score (e.g. query-log candidate features) build on."""
    scores: dict[str, float] = {}
    first_seen_order: dict[str, int] = {}
    counter = 0
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
            if doc_id not in first_seen_order:
                first_seen_order[doc_id] = counter
                counter += 1
    return scores, first_seen_order


def reciprocal_rank_fusion(rankings: Sequence[Sequence[str]], k: int = 60) -> list[str]:
    scores, first_seen_order = rrf_scores(rankings, k)
    return sorted(scores, key=lambda d: (-scores[d], first_seen_order[d]))
