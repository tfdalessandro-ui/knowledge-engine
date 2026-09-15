import pytest

from eval.weighted_fusion import weighted_fusion, weighted_fusion_scores


def test_alpha_1_reduces_to_bm25_only_order():
    bm25 = {"a": 5.0, "b": 3.0, "c": 1.0}
    vector = {"a": 0.1, "b": 0.9, "c": 0.5}  # deliberately disagrees with bm25 order
    result = weighted_fusion(bm25, vector, alpha=1.0)
    assert result == ["a", "b", "c"]


def test_alpha_0_reduces_to_vector_only_order():
    bm25 = {"a": 5.0, "b": 3.0, "c": 1.0}
    vector = {"a": 0.1, "b": 0.9, "c": 0.5}
    result = weighted_fusion(bm25, vector, alpha=0.0)
    assert result == ["b", "c", "a"]


def test_doc_only_in_one_side_still_included_via_zero_fill():
    bm25 = {"a": 5.0, "b": 3.0}
    vector = {"c": 0.9}
    result = weighted_fusion(bm25, vector, alpha=0.5)
    assert set(result) == {"a", "b", "c"}


def test_agreement_across_both_sides_wins():
    # "b" is top on both sides -- should win regardless of alpha (as long
    # as both sides contribute)
    bm25 = {"a": 5.0, "b": 6.0, "c": 1.0}
    vector = {"a": 0.2, "b": 0.9, "c": 0.5}
    result = weighted_fusion(bm25, vector, alpha=0.5)
    assert result[0] == "b"


def test_all_tied_scores_normalize_to_one_not_zero():
    bm25 = {"a": 4.0, "b": 4.0}
    vector = {"a": 0.5, "b": 0.5}
    scores = weighted_fusion_scores(bm25, vector, alpha=0.5)
    assert scores["a"] == pytest.approx(1.0)
    assert scores["b"] == pytest.approx(1.0)


def test_empty_inputs_yield_empty_result():
    assert weighted_fusion({}, {}) == []
    assert weighted_fusion_scores({}, {}) == {}


def test_invalid_alpha_raises():
    with pytest.raises(ValueError):
        weighted_fusion({"a": 1.0}, {"a": 1.0}, alpha=1.5)
    with pytest.raises(ValueError):
        weighted_fusion({"a": 1.0}, {"a": 1.0}, alpha=-0.1)
