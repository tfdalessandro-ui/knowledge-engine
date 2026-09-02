from ingest.chunking import MAX_TOKENS, MIN_TOKENS, chunk_text


def _words(n: int, prefix: str = "w") -> str:
    return " ".join(f"{prefix}{i}" for i in range(n))


def test_empty_text_yields_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_short_text_is_a_single_chunk():
    text = _words(50)
    chunks = chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0].split() == text.split()


def test_chunks_stay_within_max_tokens():
    # several paragraphs, each under max, that together exceed it many times over
    paragraphs = [_words(120, prefix=f"p{p}_") for p in range(10)]
    text = "\n\n".join(paragraphs)
    chunks = chunk_text(text)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c.split()) <= MAX_TOKENS


def test_oversized_paragraph_gets_hard_split():
    text = _words(1000)  # single paragraph, no blank lines
    chunks = chunk_text(text)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c.split()) <= MAX_TOKENS


def test_consecutive_chunks_overlap():
    paragraphs = [_words(150, prefix=f"p{p}_") for p in range(6)]
    text = "\n\n".join(paragraphs)
    chunks = chunk_text(text)
    assert len(chunks) >= 2
    for a, b in zip(chunks, chunks[1:]):
        a_words, b_words = a.split(), b.split()
        overlap = len(set(a_words[-60:]) & set(b_words[:60]))
        assert overlap > 0, "expected consecutive chunks to share some tail/head words"


def test_target_range_is_reasonable_for_typical_input():
    paragraphs = [_words(90, prefix=f"p{p}_") for p in range(8)]
    text = "\n\n".join(paragraphs)
    chunks = chunk_text(text)
    # every chunk except possibly the last should be roughly in the 250-400 band
    for c in chunks[:-1]:
        assert len(c.split()) >= MIN_TOKENS - 50  # allow some slack from paragraph granularity
