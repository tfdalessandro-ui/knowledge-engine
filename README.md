# CPU-First Knowledge Engine — P0: Foundations & Eval Harness

This is the foundation phase of a retrieval-first search system: BM25 + hybrid
search over documents, a knowledge graph, and an optional small-LLM layer on
top, all designed to run acceptably on ordinary CPU cores rather than
requiring a GPU.

**P0 does not build a search engine.** It builds the thing every later phase
needs before it can be trusted: a way to measure whether a change to the
search backend actually made results better. Without that, "is BM25 better
than the naive version" or "did hybrid search help" are just opinions.

## What's here

- **A relevance-judgment set** ([data/judgments/judgments.json](data/judgments/judgments.json)):
  63 hand-labeled (query, document, relevance-grade) triples over a 25-document
  seed corpus ([data/corpus/](data/corpus/)). This is the ground truth every
  later ranking change gets measured against.
- **An eval harness** ([src/eval/](src/eval/)): computes three standard
  retrieval-quality metrics —
  - **nDCG@10** — rewards putting the *most* relevant results at the top of
    the first page, not just any relevant result.
  - **MRR** (Mean Reciprocal Rank) — how quickly the first relevant result
    shows up.
  - **recall@20** — of everything relevant, how much was found at all.

  It runs against three deterministic stub indices (`perfect`, `shuffled`,
  `null`) rather than a real search backend, because no real backend exists
  yet — that's P1. The point of P0 is proving the *metric computation* is
  correct, on inputs where the right answer is already known.
- **A benchmark script** ([src/bench/benchmark.py](src/bench/benchmark.py)):
  a generic wrapper — `benchmark(fn, *args, **kwargs)` — that times any
  function's p50/p95 latency and tracks peak resident memory (RSS) while it
  runs. Every later phase reuses this to keep "CPU-efficient" a measured
  number, not an assumption.

## How this fits the roadmap

P0 is a hard gate. BM25 indexing, hybrid search, learning-to-rank, the
knowledge graph, connectors, web crawl, and the optional LLM layer (P1
onward) all ship changes to *how search ranks results*. None of those
changes are meaningful without this harness to score them against the
judgment set — that's the whole reason P0 comes first.

See `HELP.md` for how to run everything, and the timestamped `LOGBOOK_*.md`
files for what was actually measured and any decisions made along the way.
