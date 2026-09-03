"""Prompt construction for extractive, cited answers -- per the P7 spec:
"extractive-answer generation over retrieved passages only, with every
generated claim traceable to a source chunk id."

The prompt does the enforcement work here, not a fine-tuned model: it
instructs the model to answer ONLY from the given passages, to cite the
exact chunk_id after every claim in `[chunk_id]` form, and to say so
explicitly if the passages don't contain an answer -- rather than inventing
one. `citation.py` then verifies the model actually followed the citation
rule, since an instruction in a prompt is not a guarantee.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Passage:
    chunk_id: str
    doc_id: str
    text: str


SYSTEM_INSTRUCTIONS = (
    "You answer questions using ONLY the passages provided below. Follow these rules exactly:\n"
    "1. Every factual claim in your answer must be immediately followed by the exact chunk id "
    "of the passage that supports it, in square brackets, like this: [chunk_id].\n"
    "2. Never cite a chunk id that is not listed below.\n"
    "3. Never state a claim that is not directly supported by one of the passages.\n"
    "4. If the passages do not contain enough information to answer, say so plainly instead of guessing.\n"
    "5. Keep the answer concise -- a few sentences, not an essay."
)


def build_prompt(query: str, passages: list[Passage]) -> str:
    passage_block = "\n\n".join(f"[{p.chunk_id}] (from {p.doc_id}):\n{p.text}" for p in passages)
    return (
        f"{SYSTEM_INSTRUCTIONS}\n\n"
        f"Passages:\n{passage_block}\n\n"
        f"Question: {query}\n"
        f"Answer:"
    )
