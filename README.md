# CPU-First Knowledge Engine — P0+P1: Foundations, Eval Harness, BM25 MVP

This is a retrieval-first search system: BM25 + hybrid search over documents,
a knowledge graph, and an optional small-LLM layer on top, all designed to
run acceptably on ordinary CPU cores rather than requiring a GPU. Full
roadmap: 8 phases, P0 and P5 are hard gates, every other phase can reorder or
run in parallel.

## P0 — Foundations & evaluation harness

**P0 does not build a search engine.** It builds the thing every later phase
needs before it can be trusted: a way to measure whether a change to the
search backend actually made results better.

- **A relevance-judgment set** ([data/judgments/judgments.json](data/judgments/judgments.json)):
  79 hand-labeled (query, document, relevance-grade) triples over a
  33-document seed corpus ([data/corpus/](data/corpus/)) spanning every P1
  format (txt/md/html/csv/json/xml/docx/xlsx/pptx). This is the ground truth
  every ranking change gets measured against.
- **An eval harness** ([src/eval/](src/eval/)): computes three standard
  retrieval-quality metrics —
  - **nDCG@10** — rewards putting the *most* relevant results at the top of
    the first page, not just any relevant result.
  - **MRR** (Mean Reciprocal Rank) — how quickly the first relevant result
    shows up.
  - **recall@20** — of everything relevant, how much was found at all.

  It can run against three deterministic stub indices (`perfect`, `shuffled`,
  `null`, proving the metric math itself is correct) or the real BM25 index
  (`real`, P1's actual deliverable).
- **A benchmark script** ([src/bench/benchmark.py](src/bench/benchmark.py)):
  a generic wrapper — `benchmark(fn, *args, **kwargs)` — that times any
  function's p50/p95 latency and tracks peak resident memory (RSS) while it
  runs. Every later phase reuses this to keep "CPU-efficient" a measured
  number, not an assumption.

## P1 — Ingestion & BM25 MVP

One source type — local documents — indexed and searchable end to end, with
incremental re-indexing from day one.

- **Parsers** ([src/ingest/parsers.py](src/ingest/parsers.py)): PDF, DOCX,
  XLSX, PPTX, HTML, MD, CSV via [Docling](https://github.com/docling-project/docling)
  (one library, one unified document model); TXT/JSON/XML via small dedicated
  readers, since those formats are flat data, not laid-out documents.
- **Chunking** ([src/ingest/chunking.py](src/ingest/chunking.py)):
  paragraph-level, ~250–400 tokens (whitespace-word count) per chunk, 15%
  overlap between consecutive chunks.
- **Incremental indexing** ([src/ingest/pipeline.py](src/ingest/pipeline.py),
  [src/ingest/registry.py](src/ingest/registry.py)): a SQLite registry tracks
  each file's content hash; unchanged files are skipped entirely, a changed
  file's old chunks are deleted and replaced, new files are added, deleted
  files are removed — never a full-corpus rebuild.
- **BM25 index** ([src/ingest/index_tantivy.py](src/ingest/index_tantivy.py)):
  [Tantivy](https://github.com/quickwit-oss/tantivy), Rust BM25 search
  embedded via Python bindings, no separate server process.
- **`/search` endpoint** ([src/api/main.py](src/api/main.py)): FastAPI,
  chunk-level results (`doc_id`, `chunk_id`, score, text).

## How this fits the roadmap

BM25 indexing, hybrid search, learning-to-rank, the knowledge graph,
connectors, web crawl, and the optional LLM layer (P2 onward) all ship
changes to *how search ranks results*. None of those changes are meaningful
without the P0 harness to score them against the judgment set, and P2's
"hybrid beats BM25-only by +5% nDCG@10" exit criterion needs P1's real BM25
baseline to compare against — that's why P1's exit criterion is recording
that baseline number, not just making search technically work.

See `HELP.md` for how to run everything, and the timestamped `LOGBOOK_*.md`
files for what was actually measured and any decisions made along the way.
