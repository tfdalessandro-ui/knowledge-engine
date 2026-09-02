"""P2 benchmarks the roadmap explicitly asks for: embedding cost at ingest
time (not just query time -- the flagged risk), and hybrid query p95 latency
against a stated ceiling (the other P2 exit criterion). Uses the generic
`bench.benchmark` wrapper from P0 for both -- same instrumentation reused,
not reimplemented.

Run: PYTHONPATH=src .venv/bin/python scripts/benchmark_p2.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bench.benchmark import benchmark, print_report
from config import get_settings
from eval.hybrid_index import HybridIndex
from ingest.embeddings import embed_texts
from ingest.parsers import parse_to_text
from ingest.chunking import chunk_text

QUERY_P95_CEILING_MS = 500.0  # stated ceiling for P2's exit criterion, on this reference hardware


def collect_real_chunks(corpus_dir: Path, limit_docs: int = 15) -> list[str]:
    chunks: list[str] = []
    for path in sorted(corpus_dir.rglob("*"))[:limit_docs]:
        if not path.is_file() or path.suffix.lower() not in {".txt", ".md", ".html", ".csv", ".json", ".xml"}:
            continue
        try:
            text = parse_to_text(path)
        except Exception:  # noqa: BLE001 - skip anything that fails to parse for this benchmark
            continue
        chunks.extend(chunk_text(text))
    return chunks


def main() -> int:
    settings = get_settings()
    chunks = collect_real_chunks(settings.corpus_dir)
    print(f"collected {len(chunks)} real chunks from {settings.corpus_dir} for the embedding benchmark\n")

    # --- embedding (ingest-time) throughput ---
    batch = chunks[: min(16, len(chunks))]
    embed_texts(batch[:1])  # warm up: excludes the one-time ~15s model-load cost from the timed loop
    result = benchmark(embed_texts, batch, iterations=20, label="embed_batch")
    print_report(result)
    chunks_per_sec = len(batch) / (result.p50_ms / 1000)
    print(f"throughput    : {chunks_per_sec:.1f} chunks/sec (batch size {len(batch)})\n")

    # --- hybrid query latency ---
    hybrid = HybridIndex(settings.tantivy_index_dir, settings.faiss_index_path, settings.vector_registry_db_path)
    query_result = benchmark(hybrid.search, "bm25 ranking algorithm", 10, iterations=30, label="hybrid_query")
    print_report(query_result)
    verdict = "PASS" if query_result.p95_ms <= QUERY_P95_CEILING_MS else "FAIL"
    print(f"p95 ceiling   : {QUERY_P95_CEILING_MS:.0f} ms -> {verdict} (measured {query_result.p95_ms:.1f} ms)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
