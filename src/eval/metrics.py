"""Retrieval quality metrics: nDCG@10, MRR, recall@20.

All functions take a ranked list of doc_ids returned by a search backend and a
relevance-judgment map for the query (doc_id -> graded relevance, 0 = not judged
or irrelevant). They contain no knowledge of any particular index implementation.
"""
from __future__ import annotations

import math
from typing import Sequence

Judgments = dict[str, int]


def dcg_at_k(ranked_ids: Sequence[str], judgments: Judgments, k: int) -> float:
    total = 0.0
    for i, doc_id in enumerate(ranked_ids[:k]):
        rel = judgments.get(doc_id, 0)
        if rel <= 0:
            continue
        total += (2**rel - 1) / math.log2(i + 2)  # i is 0-indexed, rank is i+1
    return total


def ndcg_at_k(ranked_ids: Sequence[str], judgments: Judgments, k: int = 10) -> float:
    ideal_order = sorted(judgments.values(), reverse=True)[:k]
    idcg = sum((2**rel - 1) / math.log2(i + 2) for i, rel in enumerate(ideal_order) if rel > 0)
    if idcg == 0:
        return 0.0
    return dcg_at_k(ranked_ids, judgments, k) / idcg


def reciprocal_rank(ranked_ids: Sequence[str], judgments: Judgments) -> float:
    for i, doc_id in enumerate(ranked_ids):
        if judgments.get(doc_id, 0) > 0:
            return 1.0 / (i + 1)
    return 0.0


def recall_at_k(ranked_ids: Sequence[str], judgments: Judgments, k: int = 20) -> float:
    relevant = {doc_id for doc_id, rel in judgments.items() if rel > 0}
    if not relevant:
        return 0.0
    retrieved_relevant = {doc_id for doc_id in ranked_ids[:k] if doc_id in relevant}
    return len(retrieved_relevant) / len(relevant)


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0
