"""FastAPI app exposing hybrid search plus P3's query-log/selection capture.
Run with:

    uvicorn api.main:app --host <OSE_HOST> --port <OSE_PORT>   (from src/, with PYTHONPATH=.)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from config import get_settings
from eval.hybrid_index import HybridIndex
from ingest.registry import DocumentRegistry
from ltr.query_log import CandidateRecord, QueryLog

app = FastAPI(title="CPU-First Knowledge Engine", version="0.3.0")

_settings = get_settings()
_index: HybridIndex | None = None
_query_log: QueryLog | None = None
_registry: DocumentRegistry | None = None


def _get_index() -> HybridIndex:
    global _index
    if _index is None:
        # Wires the tuned Settings through -- previously built with no
        # kwargs at all, so the live service silently ran plain RRF
        # (rrf_k defaulted to 60, not the tuned rrf_k=1) regardless of
        # hybrid_fusion_mode/hybrid_alpha. See eval/hybrid_index.py's
        # docstring for the full story. hybrid_alpha_mode="adaptive" is
        # not implemented here yet -- falls back to the fixed alpha.
        _index = HybridIndex(
            _settings.tantivy_index_dir,
            _settings.faiss_index_path,
            _settings.vector_registry_db_path,
            chunk_fanout=_settings.hybrid_chunk_fanout,
            rrf_k=_settings.hybrid_rrf_k,
            fusion_mode=_settings.hybrid_fusion_mode,
            alpha=_settings.hybrid_alpha,
        )
    return _index


def _get_query_log() -> QueryLog:
    global _query_log
    if _query_log is None:
        _query_log = QueryLog(_settings.query_log_db_path)
    return _query_log


def _get_registry() -> DocumentRegistry:
    global _registry
    if _registry is None:
        _registry = DocumentRegistry(_settings.registry_db_path)
    return _registry


class SearchHit(BaseModel):
    doc_id: str
    chunk_id: str | None
    rank: int
    bm25_score: float | None
    vector_score: float | None
    rrf_score: float
    text: str | None


class SearchResponse(BaseModel):
    query_id: int
    query: str
    hits: list[SearchHit]


class SelectRequest(BaseModel):
    query_id: int
    doc_id: str
    chunk_id: str | None = None
    rank: int | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/search", response_model=SearchResponse)
def search(q: str, k: int = 10) -> SearchResponse:
    hits = _get_index().search_detailed(q, k=k)
    registry = _get_registry()

    candidates = []
    for h in hits:
        record = registry.get_by_doc_id(h.doc_id)
        candidates.append(
            CandidateRecord(
                doc_id=h.doc_id,
                chunk_id=h.chunk_id,
                rank=h.rank,
                bm25_score=h.bm25_score,
                vector_score=h.vector_score,
                rrf_score=h.rrf_score,
                source_type=record.source_type if record else None,
                ingested_at=record.ingested_at if record else None,
            )
        )
    query_id = _get_query_log().log_query(q, "hybrid", candidates)

    return SearchResponse(
        query_id=query_id,
        query=q,
        hits=[
            SearchHit(doc_id=h.doc_id, chunk_id=h.chunk_id, rank=h.rank, bm25_score=h.bm25_score,
                       vector_score=h.vector_score, rrf_score=h.rrf_score, text=h.text)
            for h in hits
        ],
    )


@app.post("/select")
def select(body: SelectRequest) -> dict:
    """Records which result a client selected for a prior /search's
    query_id -- the "result-selection capture" half of P3's deliverable.
    This is what accumulates into `ltr.train`'s training data once there's
    enough of it (see /ltr/status)."""
    if body.query_id <= 0:
        raise HTTPException(status_code=400, detail="invalid query_id")
    _get_query_log().log_selection(body.query_id, body.doc_id, body.chunk_id, body.rank)
    return {"status": "recorded"}
