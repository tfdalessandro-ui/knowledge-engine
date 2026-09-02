# HELP — running this repo

## Repo/execution split

This repo lives on the dev laptop (Windows) as the source of truth (git).
**Execution happens on sensalis-node** (Ubuntu 24.04 LTS, Python 3.12.3 — a
closer match to the CCX23 production target than the Windows dev laptop's
Python 3.13). Ship the repo over, build a venv there, run there.

Reach the node:
- On LAN: `ssh sensalis@192.168.178.65`
- Off LAN (via the CX23 reverse tunnel): `ssh -J root@157.90.229.194 -p 2222 sensalis@localhost`

Ship the repo (from the repo root on the laptop, excluding local-only dirs):

```bash
tar --exclude=.venv --exclude=.git --exclude=__pycache__ --exclude=.pytest_cache -cf - . | \
  ssh -J root@157.90.229.194 -p 2222 sensalis@localhost "tar -xf - -C ~/work/knowledge_engine"
```

(`rsync` is not available in Git Bash on Windows — plain `tar` piped over
`ssh` is the portable option that doesn't depend on a specific local tool.)

## Setup from a clean clone (laptop or node — same steps)

```bash
python3 -m venv .venv
# Linux/node/CCX23 -- torch CPU wheels FIRST (see CRITICAL note in requirements.txt:
# plain PyPI torch on Linux pulls ~1GB+ of unused CUDA/nvidia-* packages):
.venv/bin/pip install torch==2.14.0 torchvision==0.29.0 --index-url https://download.pytorch.org/whl/cpu
.venv/bin/pip install -r requirements.txt
# Windows/laptop (no CUDA-pull issue there, but same two-step order for consistency):
.venv\Scripts\pip install torch==2.14.0 torchvision==0.29.0 --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\pip install -r requirements.txt
```

`requirements.txt` is a full `pip freeze` pin set (direct deps marked in a
comment block, transitive deps below). Installing it in a clean venv should
reproduce the exact same versions on any machine — that's what makes moving
this to CCX23 later a `git clone` + `pip install`, not a re-derivation.
Verify after install with `pip list | grep torch` — it should say `2.14.0+cpu`
/ `0.29.0+cpu`, not a bare version number (which means the CUDA build slipped
through).

## Running the ingestion pipeline (P1 BM25 + P2 vectors)

```bash
PYTHONPATH=src .venv/bin/python -m ingest.pipeline              # builds/updates BOTH indices
PYTHONPATH=src .venv/bin/python -m ingest.pipeline --no-vectors  # BM25 only, skips embedding
```

Scans `data/corpus/`, parses+chunks anything new or content-changed (via a
SQLite registry keyed on SHA-256 content hash), and updates the Tantivy BM25
index at `data/tantivy_index/` AND the FAISS vector index at
`data/faiss_index/` incrementally. Prints a report:
`scanned=.. unchanged=.. added=.. updated=.. removed=.. vectors_added=.. compacted=..`.
Run it again with no changes and everything should show up as `unchanged` —
that's the incremental-indexing exit criterion made visible.

**Vector-index deletion is a tombstone, not a real delete.** FAISS's HNSW
index doesn't support `remove_ids` (confirmed directly — it raises
`RuntimeError: remove_ids not implemented for this type of index`). So a
changed/removed document's old vectors are marked deleted in
`data/vectors.db` (filtered out of every search) but stay physically in the
FAISS graph until a **compaction** rebuilds the whole vector index from only
the live vectors — this fires automatically once the tombstoned fraction
crosses `KE_VECTOR_COMPACT_THRESHOLD` (default 0.2, i.e. 20%). BM25 (Tantivy)
has no such limitation — it deletes and re-adds cleanly, no tombstoning
needed. See `src/ingest/index_faiss.py` for the full explanation.

### Network dependencies

- **PDF (P1):** Docling's PDF backend downloads OCR/layout model weights from
  HuggingFace/ModelScope **the first time it parses a PDF**, not at
  `pip install` time. Every other format (DOCX/XLSX/PPTX/HTML/MD/CSV/TXT/JSON/
  XML) is fully offline. The default `data/corpus/` has no `.pdf` file for
  exactly this reason — dropping one in and running the pipeline will trigger
  that download on first use (cached under `~/.cache/huggingface` afterward).
- **Embeddings (P2):** the BGE-Small model (~130MB) downloads from
  HuggingFace on the first `embed_texts()` call, same caching mechanism.
  Unlike PDF, this is **not gated/optional** — embeddings are P2's actual
  deliverable, so the first `ingest.pipeline` run (and the P2 tests) need
  network once. Model load itself also takes several seconds even when
  cached (confirmed ~15s on the dev laptop) — call `embed_texts()` once to
  warm it up before timing anything, or that one-time cost will dominate
  your measurement (this bit `scripts/benchmark_p2.py` during P2 development;
  see the P2 logbook).

## Running the eval harness

```bash
PYTHONPATH=src .venv/bin/python -m eval.run --index perfect   # stub, proves the metric math
PYTHONPATH=src .venv/bin/python -m eval.run --index shuffled  # stub
PYTHONPATH=src .venv/bin/python -m eval.run --index null      # stub
PYTHONPATH=src .venv/bin/python -m eval.run --index real      # BM25 only -- run ingest.pipeline first
PYTHONPATH=src .venv/bin/python -m eval.run --index hybrid     # BM25 + vector, RRF-fused -- run ingest.pipeline first
```

`--index real`/`--index hybrid` score whatever is currently in
`data/tantivy_index/` (and `data/faiss_index/` for hybrid) — run
`python -m ingest.pipeline` first or they'll score an empty index.

## Running the /search + /select API (P3 query-log capture)

```bash
PYTHONPATH=. .venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000   # run from src/
curl "http://127.0.0.1:8000/search?q=bm25+ranking&k=5"
```

`KE_HOST` / `KE_PORT` env vars override the default bind address if needed.

Every `/search` call now logs the query and its ranked candidates (BM25
score, vector score, RRF score, source type, ingestion recency) to
`data/query_log.db`, and returns a `query_id` in the response. Report a
selection against it:

```bash
curl -X POST http://127.0.0.1:8000/select -H 'Content-Type: application/json' \
  -d '{"query_id": 1, "doc_id": "doc01_bm25", "rank": 0}'
```

Check how much signal has accumulated toward the LTR training gate:

```bash
PYTHONPATH=src .venv/bin/python -m ltr.status
```

**On a real Linux server, this API is normally run under a real ASGI server
with multiple worker threads (uvicorn's default), and each request can land
on a different thread.** The three SQLite-backed singletons the API holds
(`QueryLog`, `DocumentRegistry`, the `HybridIndex`'s internal
`VectorRegistry`) are built to handle that correctly (`check_same_thread=False`
+ an explicit lock per connection) -- caught live via a test that made two
requests back-to-back and hit `sqlite3.ProgrammingError: SQLite objects
created in a thread can only be used in that same thread` before the fix.
See the comment at the top of `src/ltr/query_log.py` for the full story.

**Why P3's reranker isn't trained:** the roadmap explicitly flags starting
LTR before enough logged signal exists as a risk. This repo's query log
starts empty and stays empty until real usage happens -- `ltr.train` refuses
to fit a model below `KE_LTR_MIN_INTERACTIONS` (default 500) logged
selections and returns a clear "blocked" result instead of training on too
little data. See `src/ltr/train.py`'s module docstring.

## Running the full test suite (this is the "single documented command")

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q
```

92 passed, 1 skipped (the PDF test, see above). No prior ingest run needed —
every test that needs an index builds its own throwaway one in a temp
directory. First run needs network once, for the BGE-Small model download
(see above); after that it's fully offline. To also run the PDF test:
`KE_ENABLE_PDF_TESTS=1 PYTHONPATH=src .venv/bin/python -m pytest -q`.

- `tests/eval/test_metrics.py` — known-answer unit tests per metric.
- `tests/eval/test_harness.py` — real judgment set against the three stubs,
  asserts `null <= shuffled <= perfect`.
- `tests/eval/test_real_index_baseline.py` — builds the real BM25 index over
  `data/corpus/` and asserts/prints the P1 baseline nDCG@10/MRR/recall@20.
- `tests/eval/test_fusion.py` — Reciprocal Rank Fusion unit tests.
- `tests/eval/test_hybrid_vs_bm25.py` — the P2 exit criterion: builds both
  indices fresh and asserts hybrid beats BM25-only by >= 5% relative nDCG@10.
- `tests/bench/test_benchmark.py` — sanity-checks the benchmark wrapper.
- `tests/ingest/test_chunking.py` — chunk size bounds, overlap, hard-split
  of an over-long paragraph.
- `tests/ingest/test_parsers.py` — one test per format (except PDF).
- `tests/ingest/test_parsers_pdf.py` — PDF parsing, network-gated (see above).
- `tests/ingest/test_pipeline_incremental.py` — the P1 incremental-indexing
  exit criterion: edit one file, re-run, assert only that one file was
  touched (BM25 side).
- `tests/ingest/test_embeddings.py` — BGE-Small embedding shape/normalization,
  and why `vector_id_for_chunk` hashes text content, not just position.
- `tests/ingest/test_index_faiss.py` — FAISS add/search/persist/rebuild,
  using synthetic vectors (no network needed for this one).
- `tests/ingest/test_vector_registry.py` — the tombstone/compaction metadata
  logic in isolation.
- `tests/ingest/test_pipeline_vectors.py` — the vector side of incremental
  ingestion: tombstoning on edit, compaction firing above threshold.
- `tests/ltr/test_query_log.py` — logging queries/candidates/selections,
  training_rows() grouping and binary-label assignment.
- `tests/ltr/test_features.py` — LTR feature extraction (score defaults,
  recency computation, source-type vocab).
- `tests/ltr/test_train.py` — confirms `train_reranker` stays BLOCKED at the
  real config threshold against an empty log (production behavior), and
  separately proves the LightGBM plumbing works against synthetic data with
  a deliberately lowered threshold (not a claim the exit criterion is met).
- `tests/ltr/test_rerank.py` — loading a trained model and reordering
  candidates by predicted relevance.
- `tests/api/test_main.py` — end-to-end: builds a real index, hits `/search`
  and `/select` through a `TestClient`, confirms both get logged.

## Running the benchmark script

```bash
PYTHONPATH=src .venv/bin/python -m bench.benchmark --iterations 50 --log
```

`--log` writes a timestamped JSON result to `data/bench_logs/` (gitignored —
local artifacts, not repo content). The default sample operation is a
CPU/allocation microbenchmark with no domain meaning; the point is the
harness (`benchmark()` in `src/bench/benchmark.py`), which wraps *any*
callable:

```python
from bench.benchmark import benchmark, print_report
result = benchmark(my_function, arg1, arg2, iterations=100, label="my_op")
print_report(result)
```

Later phases call `benchmark()` directly instead of re-implementing
timing/RSS logic — see `scripts/benchmark_p2.py`, which uses it for both of
P2's flagged measurements:

```bash
PYTHONPATH=src .venv/bin/python scripts/benchmark_p2.py
```

Reports embedding throughput at ingest time (chunks/sec — the roadmap's
flagged risk: "embedding cost at ingest, not just query time") and hybrid
query p95 latency against a stated 500ms ceiling
(`QUERY_P95_CEILING_MS` in the script), printing PASS/FAIL. Measured on
sensalis-node: ~6.6 chunks/sec embedding throughput (genuinely slow on a
2-core Celeron — this is real, not a bug) and 66ms p95 query latency
(comfortably under the ceiling). **Always warm up the embedding model with
one throwaway call before timing** — the first call pays a one-time ~15s
model-load cost that will otherwise swamp your measurement (this script
does it; a lesson learned live during P2, see the logbook).

## Adding new judgment-set entries

`data/judgments/judgments.json` is a flat JSON array of
`{"query": ..., "doc_id": ..., "relevance": 0-3}` objects (0 = not relevant,
3 = highly relevant). To add entries:

1. Add or confirm the document exists in `data/corpus/<doc_id>.txt`.
2. Append judgment rows for that doc against relevant queries (existing or
   new). Grade honestly — 0 rows (explicit "not relevant") are as valuable
   as high-relevance rows, since `recall@20` and `nDCG@10` only look at what
   you graded above zero.
3. Run `pytest` — `test_judgment_set_size` enforces the 50-100 pair range
   from the P0 spec; if you blow past 100, that's a sign to trim or split.

`scripts/seed_corpus.py` (P0, 25 `.txt` docs) and `scripts/seed_corpus_p1.py`
(P1, 8 more docs in md/html/csv/json/xml/docx/xlsx/pptx) are one-time
generators for the demo corpus and don't need to be re-run — real usage is
dropping your own documents into `data/corpus/` directly. `doc_id` is
derived from the filename stem, so keep corpus filenames unique by stem.

## Reproducing on a fresh Ubuntu 24.04 box (e.g. CCX23, once it exists)

1. `git clone` this repo.
2. Confirm `python3 --version` — Ubuntu 24.04 ships Python 3.12 by default,
   matching sensalis-node's 3.12.3; no version shims needed.
3. `python3 -m venv .venv`, then install torch/torchvision from the CPU wheel
   index FIRST, then `.venv/bin/pip install -r requirements.txt` (see the
   CRITICAL note in `requirements.txt` — skipping this order pulls ~1GB+ of
   unused CUDA packages on Linux). Docling's ML stack itself is a real ~1.8GB
   install — that's expected, not a mistake.
4. `PYTHONPATH=src .venv/bin/python -m pytest -q` — should print
   `92 passed, 1 skipped`. First run needs network once (BGE-Small model
   download, ~130MB); after that it's fully offline except the one
   PDF-parsing test, which stays gated/skipped by default (see "Network
   dependencies" above).
5. Nothing in this repo hardcodes a path, host, or port — `src/config/__init__.py`
   reads everything from `KE_*` environment variables (or a `.env` file) with
   local-relative defaults, so no config edits should be needed for a basic run.
