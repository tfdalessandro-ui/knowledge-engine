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
    total_pairs = sum(len(docs) for docs in judgments_by_query.values())
    assert 50 <= total_pairs <= 100
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
