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
# Linux/node:
.venv/bin/pip install -r requirements.txt
# Windows/laptop:
.venv\Scripts\pip install -r requirements.txt
```

`requirements.txt` is a full `pip freeze` pin set (direct deps marked in a
comment block, transitive deps below). Installing it in a clean venv should
reproduce the exact same versions on any machine — that's what makes moving
this to CCX23 later a `git clone` + `pip install`, not a re-derivation.

## Running the eval harness

```bash
# Linux/node
PYTHONPATH=src .venv/bin/python -m eval.run --index perfect
PYTHONPATH=src .venv/bin/python -m eval.run --index shuffled
PYTHONPATH=src .venv/bin/python -m eval.run --index null
```

`--index` picks which stub index to score against (`perfect` sorts judged
docs by relevance and should always print 1.0000 for all three metrics;
`shuffled` returns a fixed query-agnostic order; `null` returns nothing
relevant — a deterministic worst case). There's no `real` option yet because
no real search backend exists — that's P1.

## Running the full test suite (this is the "single documented command")

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q
```

`tests/eval/test_metrics.py` has known-answer unit tests for each metric
(hand-computed expected values). `tests/eval/test_harness.py` runs the real
judgment set against all three stub indices and asserts `null <= shuffled <=
perfect`, with `perfect` pinned to exactly 1.0. `tests/bench/test_benchmark.py`
sanity-checks the benchmark wrapper itself (latency ordering, positive RSS).

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

`scripts/seed_corpus.py` is a one-time generator for the initial 25-document
demo corpus and does not need to be re-run — real usage is dropping your own
documents into `data/corpus/` directly.

## Reproducing on a fresh Ubuntu 24.04 box (e.g. CCX23, once it exists)

1. `git clone` this repo.
2. Confirm `python3 --version` — Ubuntu 24.04 ships Python 3.12 by default,
   matching sensalis-node's 3.12.3; no version shims needed.
3. `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.
4. `PYTHONPATH=src .venv/bin/python -m pytest -q` — should print `21 passed`
   with no network access required (everything here is local/offline).
5. Nothing in this repo hardcodes a path, host, or port — `src/config/__init__.py`
   reads everything from `KE_*` environment variables (or a `.env` file) with
   local-relative defaults, so no config edits should be needed for a basic run.
