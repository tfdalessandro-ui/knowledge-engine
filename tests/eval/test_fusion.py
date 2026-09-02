from eval.fusion import reciprocal_rank_fusion


def test_single_ranking_passthrough_order():
    result = reciprocal_rank_fusion([["a", "b", "c"]])
    assert result == ["a", "b", "c"]


def test_agreement_across_rankings_wins():
    # "b" is #1 in both rankings, should come out on top of the fusion
    r1 = ["a", "b", "c"]
    r2 = ["b", "c", "a"]
    result = reciprocal_rank_fusion([r1, r2])
    assert result[0] == "b"


def test_doc_only_in_one_ranking_still_included():
    r1 = ["a", "b"]
    r2 = ["c", "d"]
    result = reciprocal_rank_fusion([r1, r2])
    assert set(result) == {"a", "b", "c", "d"}


def test_empty_rankings_yield_empty_result():
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []


def test_deterministic_tie_break_uses_first_seen_order():
    # "x" and "y" never co-occur and get identical RRF scores (both rank 0
    # in a list of length 1) -- tie-break should be stable, not arbitrary
    result = reciprocal_rank_fusion([["x"], ["y"]])
    assert result == ["x", "y"]
