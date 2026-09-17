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
    """Ceiling raised 2026-09-04 (see LOGBOOK_09042026*.md): the original
    P0 spec capped this at 100 total pairs / no query-count floor beyond
    10, sized for the initial 35-document corpus. After the corpus grew to
    47 documents and repeated attempts to fix the P2 hybrid-vs-BM25 gap
    (judgment growth, GA parameter tuning) were confirmed to overfit a
    too-small judgment set via 5-fold cross-validation, the user explicitly
    asked to grow the judgment set to 100+ queries -- a deliberate,
    permanent scope change, not incremental drift. New range: 100-350
    pairs, at least 100 distinct queries. If this is ever exceeded again,
    that's the same signal as before (trim, split, or make another
    deliberate, documented scope decision), not a silent auto-raise."""
    total_pairs = sum(len(docs) for docs in judgments_by_query.values())
    assert 100 <= total_pairs <= 350
    assert len(judgments_by_query) >= 100


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
