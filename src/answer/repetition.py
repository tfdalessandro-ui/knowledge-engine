"""Guards against a real failure mode found in the 20-query P7
citation-validation batch (2026-09-08, LOGBOOK_09082026_113500.md):
greedy decoding (temperature=0.0) on a small model, once it runs out of
new content for a short factual answer, can get stuck re-emitting the
same citation marker until max_tokens cuts it off mid-token -- in 60% of
that batch, drowning a correct 1-3 sentence answer in a wall of repeated
brackets. `llm_repeat_penalty` (see config) reduces how often this
happens; this is the safety net for when it happens anyway.
"""
from __future__ import annotations

import re

# Same bracketed token repeated 3+ times in a row (2+ repeats after the
# first). A single legitimate double-citation of the same chunk (seen in
# real P7 output, e.g. "[doc32_x::0] [doc32_x::0] The benchmark...")
# stays under this threshold and is left untouched.
_REPEAT_PATTERN = re.compile(r"(\[[^\[\]]+\])(?:\s*\1){2,}")


def truncate_on_repeat(text: str) -> str:
    """Cuts `text` at the start of the first degenerate repeat run, if any.
    Returns `text` unchanged when no such run is present."""
    match = _REPEAT_PATTERN.search(text)
    if match is None:
        return text
    return text[: match.start()].rstrip()


# A second, distinct failure mode found re-running the P7 batch 2026-09-15
# (LOGBOOK_09152026_*.md) after the citation-example prompt fix: once the
# model finishes a short real answer with token budget left over, it can
# keep generating -- and having seen build_prompt's own passage block
# format ("[chunk_id] (from doc_id):\ntext", joined with blank lines)
# repeated several times in its own context, it pattern-completes by
# fabricating ENTIRE fake additional passages in that exact format,
# complete with plausible-sounding invented doc_ids and content that was
# never actually retrieved. The citation extractor then (correctly) flags
# the fabricated ids as invalid -- but the real bug is the model inventing
# whole fake source material, not just a malformed citation marker.
#
# "] (from " is the precise tell: the model's own answer text is never
# instructed to write "(from <doc_id>):" after a citation -- only
# build_prompt's passage block uses that exact phrase. A real, valid
# citation confirmed present in that same batch starts a fresh paragraph
# too ("...effectively.\n\n[doc20_web_crawling::0] more real prose"), so
# stopping on any line-starting "[" would have cut off correct answers --
# "] (from " doesn't have that false-positive risk since no legitimate
# citation is ever followed by it.
_FABRICATED_PASSAGE_PATTERN = re.compile(r"\[[^\[\]]+\]\s*\(from\s")


def truncate_on_fabricated_passage(text: str) -> str:
    """Cuts `text` at the start of the first fabricated-passage-block
    marker, if any (including that marker's own leading citation, since by
    the time "] (from " is visible the citation before it has already been
    generated). Returns `text` unchanged when no such marker is present."""
    match = _FABRICATED_PASSAGE_PATTERN.search(text)
    if match is None:
        return text
    return text[: match.start()].rstrip()
