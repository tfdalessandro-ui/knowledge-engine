from answer.repetition import truncate_on_repeat


def test_leaves_normal_answer_unchanged():
    text = "BM25 is a ranking function. [doc1::0] It predates vector search."
    assert truncate_on_repeat(text) == text


def test_leaves_a_single_legitimate_double_citation_unchanged():
    text = "[doc32_benchmark_results::0] [doc32_benchmark_results::0] The p50 latency is 0.31ms."
    assert truncate_on_repeat(text) == text


def test_truncates_at_the_start_of_a_real_degenerate_run():
    text = (
        "The roadmap has eight phases, P0 through P7. "
        "[doc33_roadmap_overview::0] [doc33_roadmap_overview::0] [doc33_roadmap_overview::0] "
        "[doc33_roadmap_overview::0] [doc33_roadmap_overview::0]"
    )
    result = truncate_on_repeat(text)
    assert result == "The roadmap has eight phases, P0 through P7."


def test_truncates_a_run_that_reaches_the_very_end_mid_token():
    text = "Answer text. [doc1::0] [doc1::0] [doc1::0] [doc1::0] [doc"
    assert truncate_on_repeat(text) == "Answer text."


def test_empty_string_is_unchanged():
    assert truncate_on_repeat("") == ""
