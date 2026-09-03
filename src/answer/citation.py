"""Citation extraction and validation -- the actual traceability check the
P7 exit criterion needs. A prompt instructing the model to cite correctly
is not proof that it did; this verifies every citation the model actually
emitted refers to a chunk_id that was genuinely in its retrieved context,
not a plausible-looking but hallucinated one.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_CITATION_PATTERN = re.compile(r"\[([^\[\]]+)\]")


def extract_citations(answer_text: str) -> list[str]:
    return _CITATION_PATTERN.findall(answer_text)


@dataclass
class CitationCheck:
    citations_found: list[str]
    valid_citations: list[str]
    invalid_citations: list[str]

    @property
    def all_valid(self) -> bool:
        return len(self.invalid_citations) == 0

    @property
    def has_any_citation(self) -> bool:
        return len(self.citations_found) > 0


def check_citations(answer_text: str, valid_chunk_ids: set[str]) -> CitationCheck:
    found = extract_citations(answer_text)
    valid = [c for c in found if c in valid_chunk_ids]
    invalid = [c for c in found if c not in valid_chunk_ids]
    return CitationCheck(citations_found=found, valid_citations=valid, invalid_citations=invalid)
