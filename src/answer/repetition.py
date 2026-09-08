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
