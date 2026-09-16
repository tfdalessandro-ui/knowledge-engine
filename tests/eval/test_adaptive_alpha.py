import pytest

from eval.adaptive_alpha import adaptive_alpha, query_length_feature


def test_query_length_feature_short_query():
    assert query_length_feature("bm25 ranking", cap=12) == pytest.approx(2 / 12)


def test_query_length_feature_caps_at_max():
    long_query = " ".join(["word"] * 20)
    assert query_length_feature(long_query, cap=12) == pytest.approx(1.0)


def test_adaptive_alpha_zero_slope_is_constant():
    short_alpha = adaptive_alpha("bm25", base=0.5, slope=0.0)
    long_alpha = adaptive_alpha("a much longer natural language question here", base=0.5, slope=0.0)
    assert short_alpha == pytest.approx(0.5)
    assert long_alpha == pytest.approx(0.5)


def test_adaptive_alpha_positive_slope_favors_bm25_for_longer_queries():
    short = adaptive_alpha("bm25", base=0.3, slope=0.4)
    long = adaptive_alpha(" ".join(["word"] * 12), base=0.3, slope=0.4)
    assert long > short


def test_adaptive_alpha_clips_to_0_1():
    assert adaptive_alpha("word " * 12, base=0.9, slope=0.9) == pytest.approx(1.0)
    assert adaptive_alpha("word", base=-0.9, slope=-0.9) == pytest.approx(0.0)
