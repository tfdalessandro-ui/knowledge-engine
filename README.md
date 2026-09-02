# CPU-First Knowledge Engine

A retrieval-first search system — BM25 + hybrid search over documents, a
knowledge graph, and an optional small-LLM layer — built to run acceptably
on ordinary CPU cores instead of requiring a GPU.

**Status:** Phase P3 infrastructure complete (P0 foundations, P1 BM25 MVP,
P2 hybrid retrieval, P3 query-log capture). P3's reranker training is
explicitly **not** done — see [Roadmap](#roadmap) for why.

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
- **Hybrid search** — [BGE-Small](https://huggingface.co/BAAI/bge-small-en-v1.5)
  CPU embeddings at ingest time, a [FAISS](https://github.com/facebookresearch/faiss)
  HNSW vector index, and Reciprocal Rank Fusion merging BM25 + vector
  results. Measured +6.6% nDCG@10 over BM25-only on the judgment set.
- **`/search` + `/select` REST endpoints** — FastAPI service over the index
  that also logs every search's ranked candidates (with BM25/vector/RRF
  scores, source type, ingestion recency) and lets a client report back
  which result was selected — the query-log capture P3's reranker will
  eventually train on.
- **LTR reranker infrastructure** — [LightGBM](https://github.com/microsoft/LightGBM)
  LambdaMART training/reranking code, feature extraction, and a status CLI —
  but explicitly gated off from running for real until 500+ logged
  interactions exist (currently 0 — no live traffic on this system yet).
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
PYTHONPATH=src .venv/bin/python -m eval.run --index real     # BM25 only
PYTHONPATH=src .venv/bin/python -m eval.run --index hybrid   # BM25 + vector, RRF-fused
```

**Serve the `/search` + `/select` API:**

```bash
cd src && PYTHONPATH=. ../.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000
curl "http://127.0.0.1:8000/search?q=bm25+ranking&k=5"   # returns a query_id alongside hits
curl -X POST http://127.0.0.1:8000/select -H 'Content-Type: application/json' \
  -d '{"query_id": 1, "doc_id": "doc01_bm25", "rank": 0}'
```

**Check LTR training-gate status:**

```bash
PYTHONPATH=src .venv/bin/python -m ltr.status
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
  eval/       nDCG@10 / MRR / recall@20 harness, stub + real + hybrid indices, RRF fusion
  ingest/     parsers, chunking, content-hash registry, Tantivy BM25 + FAISS vector indices
  ltr/        query-log/selection capture, LTR feature extraction, gated LightGBM training + reranking
tests/        pytest suite mirroring src/
data/
  corpus/     seed documents (multi-format)
  judgments/  hand-labeled query/document relevance judgments
scripts/      one-time corpus-seeding generators, P2 benchmark script
```

## Testing

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q
```

One test (PDF parsing) is gated behind `KE_ENABLE_PDF_TESTS=1` because it
triggers a one-time ML model download — see
[HELP.md](HELP.md#network-dependency-pdf-only) for why. Unlike PDF, the P2
embedding tests are NOT gated — embeddings are P2's actual deliverable, so
the first test run (or `ingest.pipeline` run) needs network once to fetch
the BGE-Small model (~130MB, cached afterward). P3's LTR tests use synthetic
data with a deliberately lowered threshold to prove the LightGBM plumbing
works — they do NOT claim the P3 exit criterion is met (it isn't, see
Roadmap below).

## Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| P0 | Foundations & evaluation harness | ✅ Done |
| P1 | Ingestion & BM25 MVP | ✅ Done |
| P2 | Hybrid retrieval (BGE-Small + FAISS/HNSW) | ✅ Done |
| P3 | Usage capture & learning-to-rank (LightGBM) | ⚠️ Infra done, training blocked |
| P4 | Entity extraction & knowledge graph v1 (spaCy + Memgraph) | Not started |
| P5 | Enterprise connectors & access control | Not started (hard gate) |
| P6 | Web crawl expansion (allowlisted sources) | Not started |
| P7 | Optional small-LLM answer layer (llama.cpp) | Not started |

P0 and P5 are hard gates — every other phase can be reordered or run in
parallel with an adjacent one. P2's exit criterion ("hybrid beats BM25-only
by +5% nDCG@10") is measured directly against P1's recorded baseline: BM25
alone scores nDCG@10 = 0.8912, hybrid scores 0.9502 — **+6.6% relative**,
comfortably clearing the bar. Hybrid query p95 latency = 66ms, well under
the 500ms ceiling stated for this hardware; embedding throughput at ingest
time is ~6.6 chunks/sec on sensalis-node's 2-core Celeron (the flagged risk
in the roadmap — ingest-time embedding cost genuinely dominates on weak
hardware, see `LOGBOOK_09032026_000504.md`).

**P3's own exit criterion ("reranking the top-50 improves nDCG@10 over RRF
alone on held-out logged queries") is explicitly NOT met, on purpose.** The
roadmap itself names this as a risk: don't train a reranker before enough
logged signal exists. This system has zero real usage — no live traffic, no
real query log — so `/search` + `/select` capture the data (with the exact
features a reranker needs: BM25 score, vector score, RRF score, source
type, ingestion recency) and `ltr.train`/`ltr.status` enforce a hard
500-interaction minimum before training runs for real (`PYTHONPATH=src
.venv/bin/python -m ltr.status` currently reports `BLOCKED (0/500
interactions)`, honestly). The LightGBM training/reranking code itself is
built and unit-tested against synthetic data (proving the plumbing works),
but that is explicitly not the same as meeting the exit criterion — see
`LOGBOOK_09032026_002053.md`.

## Documentation

- [HELP.md](HELP.md) — full setup, run, and troubleshooting reference,
  including the repo/execution split (repo on laptop, execution on
  sensalis-node) and the torch CPU-wheel install gotcha.
- `LOGBOOK_*.md` — timestamped, append-only record of what was measured and
  decided at each phase. Never overwritten in place.
