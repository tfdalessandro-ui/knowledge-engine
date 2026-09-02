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

## Running the ingestion pipeline (P1)

```bash
PYTHONPATH=src .venv/bin/python -m ingest.pipeline
```

Scans `data/corpus/`, parses+chunks anything new or content-changed (via a
SQLite registry keyed on SHA-256 content hash), and updates the Tantivy BM25
index at `data/tantivy_index/` incrementally. Prints a report:
`scanned=.. unchanged=.. added=.. updated=.. removed=..`. Run it again with
no changes and everything should show up as `unchanged` — that's the
incremental-indexing exit criterion made visible.

### Network dependency (PDF only)

Docling's PDF backend downloads OCR/layout model weights from
HuggingFace/ModelScope **the first time it parses a PDF**, not at
`pip install` time. Every other format (DOCX/XLSX/PPTX/HTML/MD/CSV/TXT/JSON/
XML) is fully offline. The default `data/corpus/` has no `.pdf` file for
exactly this reason — dropping one in and running the pipeline will trigger
that download on first use (cached under `~/.cache/huggingface` afterward).

## Running the eval harness

```bash
PYTHONPATH=src .venv/bin/python -m eval.run --index perfect   # stub, proves the metric math
PYTHONPATH=src .venv/bin/python -m eval.run --index shuffled  # stub
PYTHONPATH=src .venv/bin/python -m eval.run --index null      # stub
PYTHONPATH=src .venv/bin/python -m eval.run --index real      # the actual BM25 index -- run ingest.pipeline first
```

`--index real` scores whatever is currently in `data/tantivy_index/` — run
`python -m ingest.pipeline` first or it'll score an empty index.

## Running the /search API

```bash
PYTHONPATH=. .venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000   # run from src/
curl "http://127.0.0.1:8000/search?q=bm25+ranking&k=5"
```

`KE_HOST` / `KE_PORT` env vars override the default bind address if needed.

## Running the full test suite (this is the "single documented command")

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q
```

Runs fully offline (44 passed, 1 skipped — the PDF test, see above) with no
prior ingest run needed: `tests/eval/test_real_index_baseline.py` builds its
own throwaway index in a temp directory. To also run the PDF test:
`KE_ENABLE_PDF_TESTS=1 PYTHONPATH=src .venv/bin/python -m pytest -q` (needs
network on first run).

- `tests/eval/test_metrics.py` — known-answer unit tests per metric.
- `tests/eval/test_harness.py` — real judgment set against the three stubs,
  asserts `null <= shuffled <= perfect`.
- `tests/eval/test_real_index_baseline.py` — builds the real BM25 index over
  `data/corpus/` and asserts/prints the P1 baseline nDCG@10/MRR/recall@20.
- `tests/bench/test_benchmark.py` — sanity-checks the benchmark wrapper.
- `tests/ingest/test_chunking.py` — chunk size bounds, overlap, hard-split
  of an over-long paragraph.
- `tests/ingest/test_parsers.py` — one test per format (except PDF).
- `tests/ingest/test_parsers_pdf.py` — PDF parsing, network-gated (see above).
- `tests/ingest/test_pipeline_incremental.py` — the incremental-indexing exit
  criterion: edit one file, re-run, assert only that one file was touched.

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

Later phases (BM25 query latency, hybrid search, etc.) call `benchmark()`
directly instead of re-implementing timing/RSS logic.

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
   `44 passed, 1 skipped` with no network access required for the default run
   (see "Network dependency (PDF only)" above for the one skipped test).
5. Nothing in this repo hardcodes a path, host, or port — `src/config/__init__.py`
   reads everything from `KE_*` environment variables (or a `.env` file) with
   local-relative defaults, so no config edits should be needed for a basic run.
