from answer.citation import check_citations, extract_citations


def test_extracts_a_single_citation():
    assert extract_citations("BM25 is a ranking function [doc01::0].") == ["doc01::0"]


def test_extracts_multiple_citations():
    text = "BM25 [doc01::0] predates neural methods [doc02::1]."
    assert extract_citations(text) == ["doc01::0", "doc02::1"]


def test_no_citations_returns_empty_list():
    assert extract_citations("This has no citations at all.") == []


def test_all_citations_valid_when_they_match_retrieved_set():
    check = check_citations("BM25 is fast [doc01::0].", {"doc01::0", "doc02::0"})
    assert check.all_valid is True
    assert check.has_any_citation is True


def test_hallucinated_citation_is_flagged_invalid():
    check = check_citations("BM25 is fast [doc99::0].", {"doc01::0", "doc02::0"})
    assert check.all_valid is False
    assert check.invalid_citations == ["doc99::0"]


def test_no_citation_at_all_is_not_all_valid_but_also_not_flagged_invalid():
    check = check_citations("BM25 is fast.", {"doc01::0"})
    assert check.has_any_citation is False
    assert check.all_valid is True  # vacuously true -- no citation means nothing to be wrong
    assert check.invalid_citations == []


def test_mixed_valid_and_invalid_citations():
    check = check_citations("A [doc01::0] and B [doc99::0].", {"doc01::0"})
    assert check.valid_citations == ["doc01::0"]
    assert check.invalid_citations == ["doc99::0"]
    assert check.all_valid is False
