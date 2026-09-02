"""Paragraph-level chunking targeting ~250-400 tokens per chunk with 15%
overlap between consecutive chunks, per the P1 spec.

"Tokens" here means whitespace-delimited words, not a model-specific
tokenizer (e.g. BPE) -- a real tokenizer is not needed to hit a word-count
target, and this keeps the chunker dependency-free. Documented explicitly
because "~250-400 tokens" reads differently depending on which tokenizer you
assume.
"""
from __future__ import annotations

import re

MIN_TOKENS = 250
MAX_TOKENS = 400
TARGET_TOKENS = 325
OVERLAP_RATIO = 0.15

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")


def _split_paragraphs(text: str) -> list[str]:
    paragraphs = [p.strip() for p in _PARAGRAPH_SPLIT.split(text)]
    return [p for p in paragraphs if p]


def _words(text: str) -> list[str]:
    return text.split()


def _hard_split(words: list[str], max_tokens: int, overlap: int) -> list[list[str]]:
    """Split an over-long paragraph's word list into fixed windows, since a
    single paragraph longer than max_tokens can't be packed as one unit."""
    if not words:
        return []
    chunks = []
    start = 0
    step = max(1, max_tokens - overlap)
    while start < len(words):
        chunks.append(words[start : start + max_tokens])
        if start + max_tokens >= len(words):
            break
        start += step
    return chunks


def chunk_text(
    text: str,
    min_tokens: int = MIN_TOKENS,
    max_tokens: int = MAX_TOKENS,
    overlap_ratio: float = OVERLAP_RATIO,
) -> list[str]:
    paragraphs = _split_paragraphs(text)
    if not paragraphs:
        return []

    chunks_words: list[list[str]] = []
    current: list[str] = []

    def flush():
        if current:
            chunks_words.append(list(current))

    for para in paragraphs:
        para_words = _words(para)
        if len(para_words) > max_tokens:
            flush()
            current = []
            overlap_n = int(round(max_tokens * overlap_ratio))
            chunks_words.extend(_hard_split(para_words, max_tokens, overlap_n))
            continue

        if current and len(current) + len(para_words) > max_tokens:
            flush()
            overlap_n = int(round(len(current) * overlap_ratio))
            current = current[-overlap_n:] if overlap_n else []

        current.extend(para_words)

    flush()

    return [" ".join(w) for w in chunks_words if w]
