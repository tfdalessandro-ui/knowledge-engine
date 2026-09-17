"""Ties retrieval (P2's HybridIndex) + generation (llama.cpp) + citation
validation into the P7 answer layer: retrieve passages, ask the model to
answer extractively with citations, verify every citation it produced
actually traces back to a retrieved chunk id.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from answer.citation import CitationCheck, check_citations
from answer.model import generate
from answer.prompt import Passage, build_prompt
from eval.hybrid_index import HybridIndex


@dataclass
class AnswerResult:
    query: str
    answer_text: str
    retrieved_chunk_ids: list[str]
    citation_check: CitationCheck


class AnswerEngine:
    def __init__(
        self,
        index: HybridIndex,
        model_path: Path,
        n_ctx: int = 4096,
        max_tokens: int = 512,
        temperature: float = 0.0,
        repeat_penalty: float = 1.15,
    ):
        self._index = index
        self._model_path = model_path
        self._n_ctx = n_ctx
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._repeat_penalty = repeat_penalty

    def answer(self, query: str, k: int = 5) -> AnswerResult:
        hits = self._index.search_detailed(query, k=k)
        passages = [Passage(chunk_id=h.chunk_id, doc_id=h.doc_id, text=h.text or "") for h in hits if h.chunk_id]
        retrieved_chunk_ids = [p.chunk_id for p in passages]

        prompt = build_prompt(query, passages)
        answer_text = generate(
            prompt, self._model_path, n_ctx=self._n_ctx, max_tokens=self._max_tokens,
            temperature=self._temperature, repeat_penalty=self._repeat_penalty,
        )
        citation_check = check_citations(answer_text, set(retrieved_chunk_ids))

        return AnswerResult(
            query=query, answer_text=answer_text, retrieved_chunk_ids=retrieved_chunk_ids, citation_check=citation_check
        )


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from config import get_settings

    parser = argparse.ArgumentParser(description="Ask a question over the indexed corpus (P7 answer layer)")
    parser.add_argument("query")
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args(argv)

    settings = get_settings()
    if not settings.llm_model_path.exists():
        print(f"model not found at {settings.llm_model_path} -- see HELP.md to download it. "
              f"P7 is optional: every other feature of this project works without it.")
        return 1

    index = HybridIndex(settings.tantivy_index_dir, settings.faiss_index_path, settings.vector_registry_db_path)
    engine = AnswerEngine(
        index, settings.llm_model_path, settings.llm_n_ctx, settings.llm_max_tokens,
        settings.llm_temperature, settings.llm_repeat_penalty,
    )
    result = engine.answer(args.query, k=args.k)

    print(f"Q: {result.query}")
    print(f"A: {result.answer_text}")
    print(f"retrieved chunks: {result.retrieved_chunk_ids}")
    print(f"citations: {result.citation_check.citations_found} "
          f"(valid={result.citation_check.valid_citations}, invalid={result.citation_check.invalid_citations})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
