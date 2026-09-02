"""BM25 index over document chunks, backed by Tantivy (the P1 tech choice).

A doc_id maps 1:many to chunk_ids. Incremental re-indexing works by deleting
every chunk for a doc_id (one delete_documents call on the raw-tokenized
doc_id field) and re-adding its current chunks -- this replaces exactly one
document's worth of index content, not the whole index.
"""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import tantivy


class Hit(NamedTuple):
    score: float
    doc_id: str
    chunk_id: str
    chunk_index: int
    text: str


def _build_schema() -> "tantivy.Schema":
    sb = tantivy.SchemaBuilder()
    sb.add_text_field("doc_id", stored=True, tokenizer_name="raw")
    sb.add_text_field("chunk_id", stored=True, tokenizer_name="raw")
    sb.add_unsigned_field("chunk_index", stored=True)
    sb.add_text_field("text", stored=True, tokenizer_name="default")
    return sb.build()


class BM25Index:
    def __init__(self, index_dir: Path):
        index_dir.mkdir(parents=True, exist_ok=True)
        self.schema = _build_schema()
        self.index = tantivy.Index(self.schema, path=str(index_dir), reuse=True)
        self._writer = None

    def _writer_handle(self):
        if self._writer is None:
            self._writer = self.index.writer()
        return self._writer

    def delete_doc(self, doc_id: str) -> None:
        self._writer_handle().delete_documents("doc_id", doc_id)

    def add_chunks(self, doc_id: str, chunks: list[str]) -> None:
        writer = self._writer_handle()
        for i, chunk in enumerate(chunks):
            writer.add_document(
                tantivy.Document(
                    doc_id=doc_id,
                    chunk_id=f"{doc_id}::{i}",
                    chunk_index=i,
                    text=chunk,
                )
            )

    def commit(self) -> None:
        if self._writer is not None:
            self._writer.commit()
            self._writer = None
        self.index.reload()

    def doc_count(self) -> int:
        self.index.reload()
        return self.index.searcher().num_docs

    def search(self, query: str, limit: int = 20) -> list[Hit]:
        self.index.reload()
        searcher = self.index.searcher()
        parsed = self.index.parse_query(query, ["text"])
        result = searcher.search(parsed, limit=limit)
        hits = []
        for score, addr in result.hits:
            d = searcher.doc(addr).to_dict()
            hits.append(
                Hit(
                    score=score,
                    doc_id=d["doc_id"][0],
                    chunk_id=d["chunk_id"][0],
                    chunk_index=d["chunk_index"][0],
                    text=d["text"][0],
                )
            )
        return hits
