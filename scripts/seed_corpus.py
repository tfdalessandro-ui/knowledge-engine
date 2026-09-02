"""One-time generator for the P0 demo seed corpus (data/corpus/*.txt).

This exists only because the repo starts with zero local documents. Real usage
per HELP.md is: drop your own files into data/corpus/ and hand-label judgments
against them directly -- you do not need to run this script again.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIR = REPO_ROOT / "data" / "corpus"

DOCS: dict[str, str] = {
    "doc01_bm25": (
        "BM25 is a bag-of-words ranking function used by search engines to estimate "
        "the relevance of a document to a query. It builds on TF-IDF by adding term "
        "frequency saturation and document length normalization, controlled by the "
        "parameters k1 and b. BM25 remains a strong, cheap baseline for keyword search "
        "and is the standard first stage before any learning-to-rank layer."
    ),
    "doc02_tfidf": (
        "TF-IDF weighs a term by how often it appears in a document (term frequency) "
        "against how rare it is across the whole collection (inverse document frequency). "
        "It is the classical predecessor to BM25 and still shows up as a feature in "
        "modern hybrid ranking pipelines."
    ),
    "doc03_ndcg": (
        "Normalized Discounted Cumulative Gain (nDCG) is a ranking-quality metric that "
        "rewards placing highly relevant documents near the top of a result list. It "
        "discounts relevance logarithmically by rank position and normalizes against the "
        "ideal ordering, so scores are comparable across queries with different numbers "
        "of relevant documents."
    ),
    "doc04_mrr": (
        "Mean Reciprocal Rank (MRR) scores a ranked list by the reciprocal of the rank "
        "of the first relevant result. It is simple to compute and works well when a "
        "user only cares about finding one good answer quickly, such as a factoid "
        "question-answering system."
    ),
    "doc05_recall": (
        "Recall at k measures what fraction of all relevant documents for a query were "
        "retrieved within the top k results. Unlike precision, recall does not penalize "
        "irrelevant results in the list -- it only asks whether the relevant ones were "
        "found at all."
    ),
    "doc06_sqlite_fts5": (
        "SQLite's FTS5 extension provides full-text search directly inside a SQLite "
        "database file, with BM25-style ranking built in via the bm25() auxiliary "
        "function. It is a practical choice for CPU-first, single-node search systems "
        "that want to avoid running a separate search server."
    ),
    "doc07_fastapi": (
        "FastAPI is a Python web framework for building HTTP APIs, built on top of "
        "Starlette and Pydantic. It generates OpenAPI documentation automatically from "
        "type-annotated function signatures and supports async request handlers out of "
        "the box."
    ),
    "doc08_knowledge_graph": (
        "A knowledge graph represents entities as nodes and relationships between them "
        "as edges, allowing queries that traverse connections rather than just matching "
        "keywords. Combining a knowledge graph with text search lets a system answer "
        "questions that require joining facts across multiple documents."
    ),
    "doc09_vector_embeddings": (
        "Vector embeddings map text into a fixed-size numeric vector such that "
        "semantically similar text ends up close together in the vector space. "
        "Approximate nearest-neighbor search over embeddings is the basis of semantic "
        "search, and is often combined with keyword search in a hybrid retrieval "
        "pipeline."
    ),
    "doc10_hybrid_search": (
        "Hybrid search combines a lexical method like BM25 with a semantic method like "
        "vector similarity, then merges the two ranked lists -- often with reciprocal "
        "rank fusion -- to get results that are strong on both exact keyword matches and "
        "conceptual similarity."
    ),
    "doc11_learning_to_rank": (
        "Learning-to-rank uses machine learning to combine many ranking signals -- BM25 "
        "score, vector similarity, click history, freshness -- into a single relevance "
        "score, typically trained on labeled query-document judgment pairs like the ones "
        "in this repository's eval harness."
    ),
    "doc12_cpu_inference": (
        "CPU-first inference means designing a system so that its core retrieval path "
        "runs acceptably fast on ordinary CPU cores, without requiring a GPU. This "
        "usually means favoring lexical search and small, quantized models over large "
        "transformer models for the default path, and treating an LLM layer as optional."
    ),
    "doc13_python_venv": (
        "A Python virtual environment (venv) isolates a project's dependencies from the "
        "system Python installation. Creating one with python -m venv and installing "
        "pinned versions from a requirements file is the standard way to make a Python "
        "project's setup reproducible on a different machine."
    ),
    "doc14_pip_pinning": (
        "Pinning exact package versions in a requirements file, typically produced with "
        "pip freeze inside a clean virtual environment, ensures that installing the same "
        "requirements file on a different machine reproduces the same dependency "
        "versions rather than picking up whatever the latest releases happen to be."
    ),
    "doc15_hetzner_ccx": (
        "Hetzner's CCX line offers dedicated-vCPU cloud servers, as opposed to the "
        "shared-vCPU CX line. A CCX23 instance provides 4 dedicated vCPU cores and 16GB "
        "RAM, which avoids the noisy-neighbor CPU contention that shared-core instances "
        "can experience under sustained load."
    ),
    "doc16_rss_memory": (
        "Resident Set Size (RSS) is the portion of a process's memory that is held in "
        "physical RAM, as opposed to swapped out or never-touched virtual memory. "
        "Measuring peak RSS during a benchmark run reveals a program's real memory "
        "footprint under load, which matters on memory-constrained servers."
    ),
    "doc17_latency_percentiles": (
        "p50 and p95 latency are percentile summaries of a set of measured response "
        "times: p50 is the median, and p95 is the value below which 95 percent of "
        "requests fall. Reporting both, rather than just an average, exposes tail "
        "latency that an average would hide."
    ),
    "doc18_ubuntu_2404": (
        "Ubuntu 24.04 LTS (Noble Numbat) is a long-term-support release that ships with "
        "Python 3.12 as its default system Python interpreter, and receives security "
        "updates for five years from its release date, making it a common choice for "
        "production server deployments."
    ),
    "doc19_document_chunking": (
        "Document chunking splits long text into smaller passages before indexing, so "
        "that a search system can return a focused excerpt rather than an entire long "
        "document. Chunk size is a tradeoff: too small loses context, too large dilutes "
        "relevance signal and wastes index space."
    ),
    "doc20_web_crawling": (
        "A web crawler systematically fetches pages starting from a set of seed URLs, "
        "following links while respecting robots.txt and rate limits, to build a corpus "
        "for indexing. Crawling is a separate concern from ranking: a crawler decides "
        "what gets indexed, not how it gets ranked."
    ),
    "doc21_precision": (
        "Precision measures what fraction of the documents retrieved by a search were "
        "actually relevant. It is the counterpart to recall: a system can have perfect "
        "precision by returning only one correct result, or perfect recall by returning "
        "every document in the collection, so the two are usually reported together."
    ),
    "doc22_evaluation_harness": (
        "An evaluation harness runs a fixed set of relevance judgments -- query and "
        "document pairs with a human-assigned relevance grade -- against a search "
        "backend, and computes standard metrics like nDCG, MRR, and recall. Building "
        "this harness before the real search backend exists lets every later ranking "
        "change be measured against a stable baseline instead of judged by eye."
    ),
    "doc23_reciprocal_rank_fusion": (
        "Reciprocal rank fusion combines multiple ranked lists into one by scoring each "
        "document by the sum of 1 divided by (a constant plus its rank) across the "
        "lists it appears in. It requires no score calibration between the source "
        "rankers, which makes it a common default for merging lexical and vector search "
        "results."
    ),
    "doc24_quantized_models": (
        "Quantizing a neural network reduces the numeric precision of its weights, for "
        "example from 32-bit floats to 8-bit integers, shrinking its memory footprint "
        "and speeding up inference on CPUs at some cost to accuracy. This is one of the "
        "main techniques for running small language models without a GPU."
    ),
    "doc25_index_freshness": (
        "Index freshness describes how quickly a search index reflects changes to the "
        "underlying documents. A batch-rebuilt index may lag hours or days behind "
        "source changes, while an incrementally updated index can reflect new or edited "
        "documents within seconds, at the cost of more complex update logic."
    ),
}


def main() -> int:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for doc_id, text in DOCS.items():
        path = CORPUS_DIR / f"{doc_id}.txt"
        if path.exists():
            continue
        path.write_text(text, encoding="utf-8")
        written += 1
    print(f"wrote {written} new document(s) to {CORPUS_DIR} ({len(DOCS)} total in seed set)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
