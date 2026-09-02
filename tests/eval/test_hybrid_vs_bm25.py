"""P2 exit criterion: hybrid (BM25 + vector, RRF-fused) beats BM25-only by a
defined margin (+5% nDCG@10) on the P0/P1 judgment set, over the real
corpus. Builds both indices fresh in a temp directory -- an integration
test by nature, and needs network on first run for the embedding model
(see test_embeddings.py docstring).
"""
from pathlib import Path

import pytest

from eval.metrics import mean, ndcg_at_k, reciprocal_rank, recall_at_k
from eval.hybrid_index import HybridIndex
from eval.real_index import RealBM25Index
from eval.stub_index import load_judgments
from ingest.pipeline import run_ingest

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = REPO_ROOT / "data" / "corpus"
JUDGMENTS_PATH = REPO_ROOT / "data" / "judgments" / "judgments.json"
MIN_RELATIVE_IMPROVEMENT = 0.05  # the roadmap's "+5% nDCG@10" exit criterion


def _score(index, judgments_by_query):
    ndcgs, rrs, recalls = [], [], []
    for query, judgments in judgments_by_query.items():
        ranked = index.search(query, k=20)
        ndcgs.append(ndcg_at_k(ranked, judgments, 10))
        rrs.append(reciprocal_rank(ranked, judgments))
        recalls.append(recall_at_k(ranked, judgments, 20))
    return {"nDCG@10": mean(ndcgs), "MRR": mean(rrs), "recall@20": mean(recalls)}


@pytest.fixture(scope="module")
def built_indices(tmp_path_factory):
    tmp_dir = tmp_path_factory.mktemp("hybrid_vs_bm25")
    report = run_ingest(
        CORPUS_DIR,
        tmp_dir / "index",
        tmp_dir / "registry.db",
        vector_index_path=tmp_dir / "vectors" / "index.faiss",
        vector_registry_db=tmp_dir / "vectors.db",
    )
    assert not report.errors, f"ingest errors: {report.errors}"
    assert report.vectors_added == report.scanned  # fresh build, every chunk embedded

    bm25_only = RealBM25Index(tmp_dir / "index")
    hybrid = HybridIndex(tmp_dir / "index", tmp_dir / "vectors" / "index.faiss", tmp_dir / "vectors.db")
    return bm25_only, hybrid


def test_hybrid_beats_bm25_only_by_5_percent_ndcg10(built_indices):
    bm25_only, hybrid = built_indices
    judgments_by_query = load_judgments(JUDGMENTS_PATH)

    bm25_scores = _score(bm25_only, judgments_by_query)
    hybrid_scores = _score(hybrid, judgments_by_query)

    relative_improvement = (hybrid_scores["nDCG@10"] - bm25_scores["nDCG@10"]) / bm25_scores["nDCG@10"]

    print(f"\nP2 exit criterion: BM25-only nDCG@10={bm25_scores['nDCG@10']:.4f} "
          f"vs hybrid nDCG@10={hybrid_scores['nDCG@10']:.4f} "
          f"({relative_improvement:+.1%} relative)")
    print(f"BM25-only: {bm25_scores}")
    print(f"Hybrid:    {hybrid_scores}")

    assert relative_improvement >= MIN_RELATIVE_IMPROVEMENT, (
        f"hybrid only improved nDCG@10 by {relative_improvement:.1%}, "
        f"below the {MIN_RELATIVE_IMPROVEMENT:.0%} exit criterion"
    )
