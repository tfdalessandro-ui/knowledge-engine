# CPU-First Knowledge Engine

A retrieval-first search system — BM25 + hybrid search over documents, a
knowledge graph, and an optional small-LLM layer — built to run acceptably
on ordinary CPU cores instead of requiring a GPU.

**Status:** Phase P1 complete (P0 foundations + P1 BM25 MVP). See
[Roadmap](#roadmap).

## Table of contents

- [Features](#features)
- [Quick start](#quick-start)
- [Usage](#usage)
- [Project structure](#project-structure)
- [Testing](#testing)
- [Roadmap](#roadmap)
- [Documentation](#documentation)

## Features

- **Evaluation harness** — nDCG@10, MRR, and recall@20 computed against a
  hand-labeled judgment set, so every later ranking change is measured, not
  guessed at.
- **Multi-format ingestion** — PDF, DOCX, XLSX, PPTX, HTML, Markdown, and CSV
  via [Docling](https://github.com/docling-project/docling); TXT, JSON, and
  XML via dedicated lightweight readers.
- **Incremental indexing** — a SQLite content-hash registry means an
  unchanged file is never re-parsed or re-indexed; a changed file only
  replaces its own chunks.
- **BM25 search** — powered by [Tantivy](https://github.com/quickwit-oss/tantivy),
  embedded directly (no separate search server process).
- **`/search` REST endpoint** — a minimal FastAPI service over the index.
- **Benchmarking** — a generic `benchmark(fn, *args, **kwargs)` wrapper
  reports p50/p95 latency and peak RSS for any operation, reused across every
  phase so "CPU-efficient" stays a measured claim.

## Quick start

Requires Python 3.11+ (developed against 3.12/3.13; see
[HELP.md](HELP.md#reproducing-on-a-fresh-ubuntu-2404-box-eg-ccx23-once-it-exists)
for exact version notes).

```bash
python3 -m venv .venv

# Install torch's CPU wheels FIRST (see the CRITICAL note in requirements.txt —
# plain PyPI torch on Linux pulls ~1GB+ of unused CUDA packages otherwise):
.venv/bin/pip install torch==2.14.0 torchvision==0.29.0 --index-url https://download.pytorch.org/whl/cpu
.venv/bin/pip install -r requirements.txt

# Build the BM25 index over data/corpus/
PYTHONPATH=src .venv/bin/python -m ingest.pipeline

# Run the test suite (44 passed, 1 skipped by default)
PYTHONPATH=src .venv/bin/python -m pytest -q
```

On Windows, substitute `.venv\Scripts\pip` / `.venv\Scripts\python`.

## Usage

**Search the index from the CLI:**

```bash
PYTHONPATH=src .venv/bin/python -m eval.run --index real
```

**Serve the `/search` API:**

```bash
cd src && PYTHONPATH=. ../.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000
curl "http://127.0.0.1:8000/search?q=bm25+ranking&k=5"
```

**Benchmark any function:**

```python
from bench.benchmark import benchmark, print_report
result = benchmark(my_function, arg1, arg2, iterations=100, label="my_op")
print_report(result)
```

Full command reference, including how to add corpus documents and judgment
entries, is in [HELP.md](HELP.md).

## Project structure

```
src/
  api/        FastAPI /search endpoint
  bench/      generic latency + peak-RSS benchmark wrapper
  config/     env-var-driven settings (no hardcoded paths/ports)
  eval/       nDCG@10 / MRR / recall@20 harness, stub + real indices
  ingest/     parsers, chunking, content-hash registry, Tantivy BM25 index
tests/        pytest suite mirroring src/
data/
  corpus/     seed documents (multi-format)
  judgments/  hand-labeled query/document relevance judgments
scripts/      one-time corpus-seeding generators
```

## Testing

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q
```

Runs fully offline by default. One test (PDF parsing) is gated behind
`KE_ENABLE_PDF_TESTS=1` because it triggers a one-time ML model download —
see [HELP.md](HELP.md#network-dependency-pdf-only) for why.

## Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| P0 | Foundations & evaluation harness | ✅ Done |
| P1 | Ingestion & BM25 MVP | ✅ Done |
| P2 | Hybrid retrieval (BGE-Small + FAISS/HNSW) | Not started |
| P3 | Usage capture & learning-to-rank (LightGBM) | Not started |
| P4 | Entity extraction & knowledge graph v1 (spaCy + Memgraph) | Not started |
| P5 | Enterprise connectors & access control | Not started (hard gate) |
| P6 | Web crawl expansion (allowlisted sources) | Not started |
| P7 | Optional small-LLM answer layer (llama.cpp) | Not started |

P0 and P5 are hard gates — every other phase can be reordered or run in
parallel with an adjacent one. P2's exit criterion ("hybrid beats BM25-only
by +5% nDCG@10") is measured directly against P1's recorded baseline
(nDCG@10 = 0.8911).

## Documentation

- [HELP.md](HELP.md) — full setup, run, and troubleshooting reference,
  including the repo/execution split (repo on laptop, execution on
  sensalis-node) and the torch CPU-wheel install gotcha.
- `LOGBOOK_*.md` — timestamped, append-only record of what was measured and
  decided at each phase. Never overwritten in place.
