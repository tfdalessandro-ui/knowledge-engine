from answer.prompt import Passage, build_prompt


def test_prompt_includes_the_query():
    prompt = build_prompt("What is BM25?", [Passage("doc01::0", "doc01", "BM25 is a ranking function.")])
    assert "What is BM25?" in prompt


def test_prompt_includes_each_passage_text_and_chunk_id():
    passages = [
        Passage("doc01::0", "doc01", "BM25 is a ranking function."),
        Passage("doc02::0", "doc02", "TF-IDF predates BM25."),
    ]
    prompt = build_prompt("q", passages)
    assert "BM25 is a ranking function." in prompt
    assert "TF-IDF predates BM25." in prompt
    assert "[doc01::0]" in prompt
    assert "[doc02::0]" in prompt


def test_prompt_instructs_citation_requirement():
    prompt = build_prompt("q", [Passage("doc01::0", "doc01", "text")])
    assert "chunk id" in prompt.lower()
    assert "square brackets" in prompt.lower()


def test_prompt_instructs_refusal_when_unsupported():
    prompt = build_prompt("q", [Passage("doc01::0", "doc01", "text")])
    assert "say so" in prompt.lower() or "do not contain" in prompt.lower()


def test_prompt_with_no_passages_still_builds():
    prompt = build_prompt("q", [])
    assert "Question: q" in prompt
