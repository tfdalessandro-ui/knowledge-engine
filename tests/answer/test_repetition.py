from answer.repetition import truncate_on_fabricated_passage, truncate_on_repeat


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


def test_leaves_normal_answer_with_paragraph_citation_unchanged():
    # Real, valid P7 output (2026-09-15 batch): a legitimate citation
    # starting a fresh paragraph, with more real prose after it -- must
    # NOT be truncated just because it starts a new line.
    text = "Chunking splits documents before indexing them effectively.\n\n[doc20_web_crawling::0] This lets each piece be scored independently."
    assert truncate_on_fabricated_passage(text) == text


def test_truncates_a_real_fabricated_passage_block():
    # Real P7 output (2026-09-15 batch, "layered proximity graph structure
    # for nearest neighbor search"): a correct answer followed by an
    # entirely invented extra "passage" in build_prompt's own format.
    text = (
        "This structure allows searches starting from a high-level node, "
        "moving towards closer neighbors until reaching promising candidates "
        "[doc09_vector_embeddings::0]. This strategy is described as greedy "
        "navigation where locally better nodes are chosen repeatedly using "
        "graph structures.\n\n"
        "[https_en_wikipedia_org_wiki_Curse_of_dimensionality_86754123::9] "
        "(from https_en_wikipedia_org_wiki_Curse_of_dimensionality_86754123):\n"
        "In mathematics, computer science and statistics the curse of "
        "dimensionality refers to..."
    )
    result = truncate_on_fabricated_passage(text)
    assert result == (
        "This structure allows searches starting from a high-level node, "
        "moving towards closer neighbors until reaching promising candidates "
        "[doc09_vector_embeddings::0]. This strategy is described as greedy "
        "navigation where locally better nodes are chosen repeatedly using "
        "graph structures."
    )
    assert "Curse_of_dimensionality" not in result


def test_empty_string_is_unchanged_for_fabricated_passage_check():
    assert truncate_on_fabricated_passage("") == ""
