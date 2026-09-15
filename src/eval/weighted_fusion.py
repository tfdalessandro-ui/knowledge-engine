"""Weighted score fusion: an alternative to Reciprocal Rank Fusion
(`fusion.py`) that combines BM25 and vector scores DIRECTLY, rather than
by rank alone. RRF deliberately throws away score magnitude (only rank
order matters) specifically because BM25 and cosine similarity aren't on
comparable raw scales -- this module keeps the magnitude information by
min-max normalizing each side to [0,1] within the query's own candidate
set first (CombSum-style, a standard IR fusion technique), then combines
them as `alpha * norm_bm25 + (1 - alpha) * norm_vector`. A doc present in
only one side gets 0 for the missing side (zero-fill), not excluded --
same "still included" behavior as RRF, just scored differently.

Explored 2026-09-04 (see LOGBOOK_09042026_*.md) as a candidate replacement
for RRF after RRF-with-tuned-rrf_k=1 was deployed but still fell short of
P2's +5% exit criterion. See that logbook for whether it was found to
beat the deployed RRF configuration and whether it was itself deployed.
"""
from __future__ import annotations


def _normalize(scored: dict[str, float]) -> dict[str, float]:
    """Min-max to [0,1]. All-tied scores normalize to 1.0 (equally
    maximal), not 0 -- a single-candidate list or a list of identical
    scores shouldn't be zeroed out just because there's no spread."""
    if not scored:
        return {}
    values = scored.values()
    lo, hi = min(values), max(values)
    if hi == lo:
        return {doc_id: 1.0 for doc_id in scored}
    return {doc_id: (v - lo) / (hi - lo) for doc_id, v in scored.items()}


def weighted_fusion_scores(
    bm25_scored: dict[str, float],
    vector_scored: dict[str, float],
    alpha: float = 0.5,
) -> dict[str, float]:
    """`bm25_scored`/`vector_scored`: raw score per doc_id (already
    collapsed to one score per doc, e.g. the best chunk's score) from each
    side's own candidate list. `alpha` weights the BM25 side; `(1 - alpha)`
    weights the vector side. Returns the fused score per doc_id (union of
    both sides' doc_ids)."""
    if not 0.0 <= alpha <= 1.0:
        raise ValueError(f"alpha must be in [0, 1], got {alpha!r}")
    norm_bm25 = _normalize(bm25_scored)
    norm_vector = _normalize(vector_scored)
    doc_ids = set(norm_bm25) | set(norm_vector)
    return {
        doc_id: alpha * norm_bm25.get(doc_id, 0.0) + (1 - alpha) * norm_vector.get(doc_id, 0.0)
        for doc_id in doc_ids
    }


def weighted_fusion(
    bm25_scored: dict[str, float],
    vector_scored: dict[str, float],
    alpha: float = 0.5,
) -> list[str]:
    scores = weighted_fusion_scores(bm25_scored, vector_scored, alpha)
    return sorted(scores, key=lambda d: -scores[d])
