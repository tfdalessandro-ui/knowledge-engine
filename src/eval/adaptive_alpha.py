"""Adaptive alpha: instead of one fixed constant weighting BM25 vs. vector
scores in `weighted_fusion.py`, compute alpha per query as a simple linear
function of a cheap query feature (word count) -- the intuition being
short, keyword/entity-style queries might benefit from trusting BM25 more,
while longer natural-language questions might benefit from trusting
vector similarity more.

Deliberately kept to the simplest possible model (2 free parameters: a
base and a slope over one normalized feature) -- fork point #3 from
LOGBOOK_09042026_060353.md flagged this as unexplored, and this
investigation's own prior rounds showed that adding search-space
complexity without enough held-out data to validate it is exactly how
overfitting happens (see LOGBOOK_09032026_161900.md's round-1 GA result).
A 2-parameter linear model over 106 queries / ~21 held-out per fold is
already close to the edge of what's trustworthy here; anything richer
(more features, a nonlinear model) would need a larger judgment set
first, not attempted in this module.

See LOGBOOK_09042026_*.md for whether this was found to beat the fixed
alpha=0.535 currently deployed, and whether it was itself deployed.
"""
from __future__ import annotations


def query_length_feature(query: str, cap: int = 12) -> float:
    """Word count normalized to [0,1], capped at `cap` words so a very
    long query doesn't dominate the linear model unboundedly."""
    n = len(query.split())
    return min(n, cap) / cap


def adaptive_alpha(query: str, base: float, slope: float, cap: int = 12) -> float:
    """alpha = clip(base + slope * normalized_word_count, 0, 1). A
    positive slope means longer queries lean more toward BM25 (alpha
    closer to 1); negative means longer queries lean more toward vector
    similarity -- which direction is actually better, if either, is an
    empirical question this module doesn't presuppose an answer to."""
    feature = query_length_feature(query, cap=cap)
    return max(0.0, min(1.0, base + slope * feature))
