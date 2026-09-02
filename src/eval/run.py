"""Eval harness CLI: python -m eval.run [--judgments PATH] [--corpus DIR] [--index perfect|shuffled|null]

Runs the judgment set against a chosen stub index (P1 will add a --index real
option once BM25 exists) and prints an nDCG@10 / MRR / recall@20 report.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # allow `python -m eval.run` from repo root

from config import get_settings
from eval.metrics import mean, ndcg_at_k, reciprocal_rank, recall_at_k
from eval.stub_index import NullStubIndex, PerfectStubIndex, ShuffledStubIndex, load_judgments

INDEX_CHOICES = {
    "perfect": PerfectStubIndex,
    "shuffled": ShuffledStubIndex,
    "null": NullStubIndex,
}


def build_index(name: str, judgments_by_query: dict[str, dict[str, int]]):
    all_doc_ids = sorted({doc_id for docs in judgments_by_query.values() for doc_id in docs})
    if name == "perfect":
        return PerfectStubIndex(judgments_by_query, all_doc_ids)
    if name == "shuffled":
        return ShuffledStubIndex(all_doc_ids)
    if name == "null":
        return NullStubIndex(all_doc_ids)
    raise ValueError(f"unknown stub index {name!r}, choose from {sorted(INDEX_CHOICES)}")


def run_eval(index, judgments_by_query: dict[str, dict[str, int]], k_ndcg: int = 10, k_recall: int = 20):
    ndcgs, rrs, recalls = [], [], []
    for query, judgments in judgments_by_query.items():
        ranked = index.search(query, max(k_ndcg, k_recall))
        ndcgs.append(ndcg_at_k(ranked, judgments, k_ndcg))
        rrs.append(reciprocal_rank(ranked, judgments))
        recalls.append(recall_at_k(ranked, judgments, k_recall))
    return {
        "queries": len(judgments_by_query),
        f"nDCG@{k_ndcg}": mean(ndcgs),
        "MRR": mean(rrs),
        f"recall@{k_recall}": mean(recalls),
    }


def print_report(index_name: str, results: dict) -> None:
    print(f"=== Eval report (stub index: {index_name}) ===")
    print(f"queries judged : {results['queries']}")
    for key, value in results.items():
        if key == "queries":
            continue
        print(f"{key:<12}: {value:.4f}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Retrieval eval harness (P0: stub index only)")
    parser.add_argument("--judgments", type=Path, default=None, help="path to judgments.json (default: config)")
    parser.add_argument("--index", choices=sorted(INDEX_CHOICES), default="perfect")
    args = parser.parse_args(argv)

    settings = get_settings()
    judgments_path = args.judgments or settings.judgments_path
    judgments_by_query = load_judgments(judgments_path)

    index = build_index(args.index, judgments_by_query)
    results = run_eval(index, judgments_by_query)
    print_report(args.index, results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
