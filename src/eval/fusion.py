"""Reciprocal Rank Fusion: combine several ranked lists of doc_ids into one,
without needing the source rankers' scores to be on comparable scales (BM25
and cosine similarity are not)."""
from __future__ import annotations

from typing import Sequence


def reciprocal_rank_fusion(rankings: Sequence[Sequence[str]], k: int = 60) -> list[str]:
    scores: dict[str, float] = {}
    first_seen_order: dict[str, int] = {}
    counter = 0
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
            if doc_id not in first_seen_order:
                first_seen_order[doc_id] = counter
                counter += 1
    return sorted(scores, key=lambda d: (-scores[d], first_seen_order[d]))
