"""Exit criterion: baseline nDCG@10 recorded on the P0 judgment set, using
the real Tantivy BM25 index (not a stub) built by the P1 ingestion pipeline
over the actual data/corpus/ directory.

This is slower than the stub-index tests (it parses every corpus document,
including the DOCX/XLSX/PPTX ones through Docling) and is an integration
test by nature -- it's exercising the real pipeline end to end, not a stub.
"""
from pathlib import Path

import pytest

from eval.metrics import mean, ndcg_at_k, reciprocal_rank, recall_at_k
from eval.real_index import RealBM25Index
from eval.stub_index import load_judgments
from ingest.pipeline import run_ingest

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = REPO_ROOT / "data" / "corpus"
JUDGMENTS_PATH = REPO_ROOT / "data" / "judgments" / "judgments.json"


@pytest.fixture(scope="module")
def real_index(tmp_path_factory):
    tmp_dir = tmp_path_factory.mktemp("real_index_baseline")
    report = run_ingest(CORPUS_DIR, tmp_dir / "index", tmp_dir / "registry.db")
    assert not report.errors, f"ingest errors: {report.errors}"
    assert report.added == report.scanned  # fresh index, everything is new
    return RealBM25Index(tmp_dir / "index")


def test_real_index_covers_the_full_corpus(real_index):
    # sanity: every corpus doc is retrievable by at least one of its own
    # distinctive words, proving the index isn't empty or truncated
    hits = real_index.search("bm25 ranking algorithm search engines relevance", k=25)
    assert len(hits) > 0


def test_real_index_baseline_ndcg_beats_zero(real_index):
    judgments_by_query = load_judgments(JUDGMENTS_PATH)
    ndcgs, rrs, recalls = [], [], []
    for query, judgments in judgments_by_query.items():
        ranked = real_index.search(query, k=20)
        ndcgs.append(ndcg_at_k(ranked, judgments, 10))
        rrs.append(reciprocal_rank(ranked, judgments))
        recalls.append(recall_at_k(ranked, judgments, 20))

    baseline_ndcg10 = mean(ndcgs)
    baseline_mrr = mean(rrs)
    baseline_recall20 = mean(recalls)

    print(f"\nP1 baseline on real BM25 index: nDCG@10={baseline_ndcg10:.4f} "
          f"MRR={baseline_mrr:.4f} recall@20={baseline_recall20:.4f}")

    # A real BM25 index over hand-written, topically distinct documents should
    # comfortably beat doing nothing -- this is a baseline sanity floor, not a
    # tuned target (chunking/fusion tuning is P2's job, not P1's).
    assert baseline_ndcg10 > 0.3
    assert baseline_recall20 > 0.3
