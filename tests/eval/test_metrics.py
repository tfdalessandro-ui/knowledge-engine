import math

from eval.metrics import mean, ndcg_at_k, reciprocal_rank, recall_at_k


def test_ndcg_perfect_order_is_one():
    judgments = {"a": 3, "b": 2, "c": 1}
    assert ndcg_at_k(["a", "b", "c"], judgments, k=10) == 1.0


def test_ndcg_worst_order_is_less_than_one():
    judgments = {"a": 3, "b": 2, "c": 1}
    worst = ndcg_at_k(["c", "b", "a"], judgments, k=10)
    assert 0 < worst < 1.0


def test_ndcg_no_relevant_hits_is_zero():
    judgments = {"a": 3}
    assert ndcg_at_k(["x", "y", "z"], judgments, k=10) == 0.0


def test_ndcg_empty_judgments_is_zero():
    assert ndcg_at_k(["a", "b"], {}, k=10) == 0.0


def test_ndcg_known_value_two_docs():
    # rel=[3,1] retrieved in order -> DCG = (2^3-1)/log2(2) + (2^1-1)/log2(3)
    judgments = {"a": 3, "b": 1}
    dcg = (2**3 - 1) / math.log2(2) + (2**1 - 1) / math.log2(3)
    idcg = dcg  # already ideal order
    expected = dcg / idcg
    assert ndcg_at_k(["a", "b"], judgments, k=10) == expected


def test_reciprocal_rank_first_hit():
    assert reciprocal_rank(["x", "a", "b"], {"a": 1, "b": 1}) == 0.5


def test_reciprocal_rank_no_hit_is_zero():
    assert reciprocal_rank(["x", "y"], {"a": 1}) == 0.0


def test_reciprocal_rank_immediate_hit():
    assert reciprocal_rank(["a", "x"], {"a": 1}) == 1.0


def test_recall_at_k_full_recall():
    judgments = {"a": 1, "b": 1}
    assert recall_at_k(["a", "b", "c"], judgments, k=20) == 1.0


def test_recall_at_k_partial_recall():
    judgments = {"a": 1, "b": 1}
    assert recall_at_k(["a", "x", "y"], judgments, k=20) == 0.5


def test_recall_at_k_respects_k_cutoff():
    judgments = {"a": 1, "b": 1}
    assert recall_at_k(["x", "y", "a", "b"], judgments, k=1) == 0.0


def test_recall_at_k_no_relevant_docs_is_zero():
    assert recall_at_k(["a", "b"], {}, k=20) == 0.0


def test_mean_empty_is_zero():
    assert mean([]) == 0.0


def test_mean_basic():
    assert mean([1.0, 2.0, 3.0]) == 2.0
