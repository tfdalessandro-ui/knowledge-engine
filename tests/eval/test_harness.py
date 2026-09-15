"""Known-answer tests: the harness must compute nDCG@10/MRR/recall@20
correctly against stub indices whose behavior is fully known in advance."""
from pathlib import Path

import pytest

from eval.run import build_index, run_eval
from eval.stub_index import load_judgments

REPO_ROOT = Path(__file__).resolve().parents[2]
JUDGMENTS_PATH = REPO_ROOT / "data" / "judgments" / "judgments.json"


@pytest.fixture(scope="module")
def judgments_by_query():
    assert JUDGMENTS_PATH.exists(), "run scripts/seed_corpus.py and check judgments.json is committed"
    return load_judgments(JUDGMENTS_PATH)


def test_judgment_set_size(judgments_by_query):
    # Fixed 2026-09-15 (TODO.md item 10): the original bound was `50 <= total <= 100`,
    # a snapshot of what the judgment set happened to be at P0 (committed once,
    # 2026-09-02, never revisited) -- not a deliberate ceiling. The set has grown
    # by deliberate, repeated operator decision since (79 -> 106 -> 126 queries,
    # documented in LOGBOOK_09062026_*.md), so a fixed upper bound just breaks
    # again on the next intentional growth. MIN_JUDGMENT_PAIRS stays a real floor
    # (enough for the stub-index known-answer tests below to be meaningful);
    # MAX_SANE_JUDGMENT_PAIRS is a generous corruption guard (e.g. a bug that
    # duplicates every row many times over), not a growth cap -- it should never
    # need updating just because the judgment set grew as intended.
    MIN_JUDGMENT_PAIRS = 50
    MAX_SANE_JUDGMENT_PAIRS = 5000
    total_pairs = sum(len(docs) for docs in judgments_by_query.values())
    assert MIN_JUDGMENT_PAIRS <= total_pairs <= MAX_SANE_JUDGMENT_PAIRS, (
        f"{total_pairs} judgment pairs -- expected at least {MIN_JUDGMENT_PAIRS} "
        f"(too few for the stub-index tests to be meaningful) and at most "
        f"{MAX_SANE_JUDGMENT_PAIRS} (this high only as a corruption guard, e.g. "
        f"duplicated rows -- if this is a real, deliberate judgment-set size, "
        f"raise MAX_SANE_JUDGMENT_PAIRS, don't just delete the check)"
    )
    assert len(judgments_by_query) >= 10


def test_perfect_index_scores_are_at_ceiling(judgments_by_query):
    index = build_index("perfect", judgments_by_query)
    results = run_eval(index, judgments_by_query)
    assert results["nDCG@10"] == pytest.approx(1.0)
    assert results["MRR"] == pytest.approx(1.0)
    assert results["recall@20"] == pytest.approx(1.0)


def test_null_index_scores_are_zero(judgments_by_query):
    index = build_index("null", judgments_by_query)
    results = run_eval(index, judgments_by_query)
    assert results["nDCG@10"] == 0.0
    assert results["MRR"] == 0.0
    assert results["recall@20"] == 0.0


def test_shuffled_index_is_strictly_between_null_and_perfect(judgments_by_query):
    perfect = run_eval(build_index("perfect", judgments_by_query), judgments_by_query)
    shuffled = run_eval(build_index("shuffled", judgments_by_query), judgments_by_query)
    null = run_eval(build_index("null", judgments_by_query), judgments_by_query)

    for metric in ("nDCG@10", "MRR", "recall@20"):
        assert null[metric] <= shuffled[metric] <= perfect[metric]
    assert shuffled["nDCG@10"] < perfect["nDCG@10"]
