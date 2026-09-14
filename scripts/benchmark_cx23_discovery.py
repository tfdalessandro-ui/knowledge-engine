"""Benchmark: feed the SAME brand x EU-language-intent queries that Sensalis'
doc_source_discovery.py issues on CX23 (pulled live from /root/lectura_taxonomy.json,
DOC_MAX=30) through this project's own Step 8 on-demand discovery pipeline
(src/discovery/pipeline.run_discovery), on sensalis-node, as a side-by-side
benchmark -- not a modification of CX23, not a merge of the two projects.

Read-only w.r.t. CX23. Writes only into this repo's own isolated discovery
namespace (data/discovered/, discovery_provenance.db) -- same guardrails as
every other Step 8 invocation (robots.txt, blocklist, MAX_URLS_PER_TRIGGER=3
per query). That per-query cap is NOT raised to match CX23's pooled
DOC_CAND_MAX=40-across-30-queries -- loosening a hard safety cap just to
chase apples-to-apples throughput would defeat the guardrail's purpose.

Writes each result incrementally to OUT_FILE.jsonl (one JSON object per
line, flushed immediately) so a crash mid-run doesn't lose completed work --
the summary .json at the end is a convenience, the .jsonl is authoritative.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))

from config import get_settings
from discovery.pipeline import run_discovery

QUERIES_FILE = Path(os.environ.get('BENCH_QUERIES_FILE',
    str(Path(__file__).resolve().parent.parent / 'data' / 'benchmark_cx23_queries_remaining.txt')))
OUT_FILE = Path(os.environ.get('BENCH_OUT_FILE',
    str(Path(__file__).resolve().parent.parent / 'data' / 'benchmark_cx23_discovery_results_part2.json')))


def main():
    queries = [l.strip() for l in QUERIES_FILE.read_text(encoding='utf-8').splitlines() if l.strip()]
    settings = get_settings()
    results = []
    jsonl_path = OUT_FILE.with_suffix('.jsonl')
    jf = open(jsonl_path, 'a', encoding='utf-8')
    for i, q in enumerate(queries, 1):
        print(f'=== [{i}/{len(queries)}] {q!r} ===', flush=True)
        t0 = time.time()
        try:
            report = run_discovery(q, settings, caller='benchmark:cx23-parity-20260913')
            elapsed = round(time.time() - t0, 2)
            row = {
                'query': q,
                'elapsed_s': elapsed,
                'candidates_considered': report.candidates_considered,
                'fetched': list(report.fetched),
                'skipped_blocklist': list(report.skipped_blocklist),
                'skipped_robots_disallowed': list(report.skipped_robots_disallowed),
                'errors': list(report.errors),
            }
            results.append(row)
            print(f'  -> considered={report.candidates_considered} fetched={len(report.fetched)} '
                  f'blocklist={len(report.skipped_blocklist)} robots={len(report.skipped_robots_disallowed)} '
                  f'errors={len(report.errors)} ({elapsed}s)', flush=True)
        except Exception as exc:
            elapsed = round(time.time() - t0, 2)
            print(f'  !! FAILED: {exc}', flush=True)
            row = {'query': q, 'elapsed_s': elapsed, 'error': str(exc)}
            results.append(row)
        jf.write(json.dumps(row) + '\n')
        jf.flush()
        time.sleep(1.0)
    jf.close()

    OUT_FILE.write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(f'\nWrote {len(results)} results -> {OUT_FILE}', flush=True)


if __name__ == '__main__':
    main()
