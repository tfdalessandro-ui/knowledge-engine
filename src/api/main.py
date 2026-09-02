"""FastAPI app exposing the P1 BM25 index. Run with:

    uvicorn api.main:app --host <KE_HOST> --port <KE_PORT>   (from src/, with PYTHONPATH=.)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from pydantic import BaseModel

from config import get_settings
from ingest.index_tantivy import BM25Index

app = FastAPI(title="CPU-First Knowledge Engine", version="0.1.0")

_settings = get_settings()
_index: BM25Index | None = None


def _get_index() -> BM25Index:
    global _index
    if _index is None:
        _index = BM25Index(_settings.tantivy_index_dir)
    return _index


class SearchHit(BaseModel):
    doc_id: str
    chunk_id: str
    chunk_index: int
    score: float
    text: str


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/search", response_model=SearchResponse)
def search(q: str, k: int = 10) -> SearchResponse:
    hits = _get_index().search(q, limit=k)
    return SearchResponse(
        query=q,
        hits=[SearchHit(doc_id=h.doc_id, chunk_id=h.chunk_id, chunk_index=h.chunk_index, score=h.score, text=h.text) for h in hits],
    )
