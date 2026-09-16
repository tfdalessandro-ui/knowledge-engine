# HELP — running this repo

## Repo/execution split

This repo lives on the dev laptop (Windows) as the source of truth (git).
**Execution happens on sensalis-node** (Ubuntu 24.04 LTS, Python 3.12.3),
which is also the production target — dev and prod run on the same
machine, not separate hosts. Ship the repo over, build a venv there, run
there.

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
# Linux/sensalis-node -- torch CPU wheels FIRST (see CRITICAL note in requirements.txt:
# plain PyPI torch on Linux pulls ~1GB+ of unused CUDA/nvidia-* packages):
.venv/bin/pip install torch==2.14.0 torchvision==0.29.0 --index-url https://download.pytorch.org/whl/cpu
.venv/bin/pip install -r requirements.txt
# Windows/laptop (no CUDA-pull issue there, but same two-step order for consistency):
.venv\Scripts\pip install torch==2.14.0 torchvision==0.29.0 --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\pip install -r requirements.txt
```

`requirements.txt` is a full `pip freeze` pin set (direct deps marked in a
comment block, transitive deps below). Installing it in a clean venv should
reproduce the exact same versions on any machine — that's what makes standing
up a fresh clone on sensalis-node a `git clone` + `pip install`, not a
re-derivation.
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

**Running it as a persistent service** (so it survives SSH disconnects and
reboots, not just a foreground process): a `systemctl --user` unit, not a
system-wide one under `/etc/systemd/system/` -- `sudo` on sensalis-node
needs a password this session doesn't have, so anything requiring root gets
staged for the operator rather than assumed. A user unit needs no root at
all:

```bash
mkdir -p ~/.config/systemd/user
cp deploy/ose.service ~/.config/systemd/user/   # adjust paths inside if your checkout isn't at ~/work/ose
systemctl --user daemon-reload
systemctl --user enable --now ose.service
loginctl enable-linger $(whoami)   # survives logout/reboot; succeeded without sudo on this node
systemctl --user status ose.service --no-pager
```

Verify it's actually live, not just "should work": `ps aux | grep uvicorn`,
`ss -tlnp | grep 8000`, `curl -i localhost:8000/health`, and a real query
against `/search` -- "the code exists" and "the service is running" are
different claims, and only the commands above prove the second one.

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

## Running the knowledge graph pipeline (P4)

Unlike every prior phase's index (Tantivy/FAISS embedded in-process),
**Memgraph is a separate server process** -- this repo does not start it
for you. Start it once (Docker required):

```bash
docker run -d --name memgraph_ke -p 127.0.0.1:7687:7687 --restart unless-stopped memgraph/memgraph
```

Bound to `127.0.0.1` only, matching sensalis-node's existing convention for
every other Docker service on it (confirmed by inspecting the node before
adding anything -- see the P4 logbook). `KE_MEMGRAPH_URI` (default
`bolt://127.0.0.1:7687`) points the pipeline at it; the standard `neo4j`
Python driver talks to it over Bolt (Memgraph is Bolt-compatible -- no
Memgraph-specific client library needed).

```bash
PYTHONPATH=src .venv/bin/python -m kg.pipeline
```

Scans `data/corpus/`, extracts entities (Company/Person/Product/Technology)
and pattern-based relations per document, resolves entities (exact match
auto-resolves; near-duplicates get queued in `data/merge_review.db` for
manual review, never auto-merged), and writes everything to Memgraph.
Prints `documents_processed=.. entities_extracted=.. relations_extracted=..
merge_candidates_queued=..`. Unlike `ingest.pipeline`, this always does a
full pass -- entity resolution needs to see the whole corpus's entity set,
not one file in isolation, and P4's corpus-scale makes that cheap.

In production this runs on a schedule (`ose-kg-extract.timer`, systemd
`--user`, daily 03:15 UTC on sensalis-node) rather than only on manual
invocation -- added 2026-09-14 after `run_kg_extraction()` was found to
have no production caller at all (see TODO.md item 5), which is also why
the second container below exists.

### A second, isolated Memgraph for tests -- do not skip this

`tests/kg/`'s own test suite needs a **separate** Memgraph instance, never
the production one above. Its fixtures call `store.clear()` in both setup
and teardown; pointed at production (as they originally were, before
2026-09-14) that wipes the live knowledge graph for real -- it happened
once. Start a second container on a different port:

```bash
docker run -d --name memgraph_ke_test -p 127.0.0.1:7688:7687 --restart unless-stopped memgraph/memgraph
```

`KE_TEST_MEMGRAPH_URI` (default `bolt://127.0.0.1:7688`, `Settings.
test_memgraph_uri`) points every `tests/kg/*` fixture at it. `tests/kg/
test_neighbor_retrieval.py`'s fixture asserts `test_memgraph_uri !=
memgraph_uri` before doing anything destructive, specifically so a future
config mistake fails loudly instead of repeating the incident.

**Why NER is a curated `EntityRuler`, not stock spaCy alone:** verified
directly (not assumed) that `en_core_web_sm` run cold over this corpus tags
"BM25" and "bm25" as PERSON and finds no real Company/Product signal --
this corpus is about search infrastructure, not people or organizations.
Technology/Company/Product are recognized via an exact-match term list
grounded in terms confirmed present in `data/corpus/` (checked with `grep`
before writing `kg/ner.py`'s `TECHNOLOGY_TERMS`/`COMPANY_TERMS`/
`PRODUCT_TERMS`), trading recall for precision -- which is exactly what the
exit criterion asks for. Person is left to spaCy's native NER with a filter
requiring 2+ alphabetic tokens (a real personal name is virtually always
"First Last"); every false positive found in testing was a single-token
span, so this removed all of them without a mechanism to lose a real name.

**Merge-review queue:** `kg.resolution.MergeReviewQueue` never auto-merges
a fuzzy match (default threshold 85, `rapidfuzz.fuzz.token_sort_ratio`) --
it queues the pair in `data/merge_review.db` for a human to accept or
reject. Inspect and resolve pending candidates:

```python
from pathlib import Path
from kg.resolution import MergeReviewQueue

queue = MergeReviewQueue(Path("data/merge_review.db"))
for candidate in queue.list_pending():
    print(candidate)  # e.g. MergeCandidate(entity_a='CCX23', entity_b='CX23', label='PRODUCT', score=88.9, ...)
    queue.resolve(candidate.candidate_id, merge=False)  # or merge=True once a human has judged it
```

### Testing against Memgraph

`tests/kg/` needs a running Memgraph instance for anything beyond pure NER/
relation-extraction/resolution logic (those three are pure Python, no
external service, and always run). Tests requiring Memgraph carry
`pytestmark = pytest.mark.requires_memgraph`; `tests/kg/conftest.py` probes
connectivity once per session and auto-skips them with a clear reason if
it's unreachable -- so `pytest -q` still passes cleanly on a machine with no
Memgraph (this repo's dev laptop has no Docker daemon running) while
exercising the real thing wherever it's up (sensalis-node).

**`tests/kg/test_neighbor_retrieval.py` is the P4 exit criterion made
concrete:** it runs the real `kg.pipeline` over the real `data/corpus/`
into Memgraph, then checks a fixed, hand-verified 20-entity set (11 with
real relations, 9 correctly isolated) against expected neighbors -- as a
parametrized test, so each of the 20 is its own pass/fail line, not one
bulk assertion.

**These tests wipe the graph.** `MemgraphStore.clear()` runs before and
after each test that touches Memgraph -- don't point `KE_MEMGRAPH_URI` at
an instance holding graph content you want to keep.

## Running the access control / Git connector (P5)

**PostgreSQL is a separate server process too**, same pattern as Memgraph
-- this repo does not start it for you:

```bash
docker run -d --name postgres_ke -p 127.0.0.1:5433:5432 -e POSTGRES_PASSWORD=ke_dev_password -e POSTGRES_DB=knowledge_engine --restart unless-stopped postgres:16-alpine
```

Bound to `127.0.0.1` on port **5433**, not 5432 -- 5432 was already taken by
an unrelated Docker workload found running on sensalis-node when this phase
started (see the P5 logbook). `POSTGRES_PASSWORD` here is a throwaway local
dev credential for a loopback-only container, not a real secret -- never
reuse it for anything that isn't this exact local setup. `KE_POSTGRES_DSN`
(default `postgresql://postgres:ke_dev_password@127.0.0.1:5433/knowledge_engine`)
points everything at it.

**Why PostgreSQL is a new store, not a migration of P1-P4's SQLite stores:**
the roadmap's P5 tech choice is "PostgreSQL (metadata store, replacing
SQLite at this scale)" -- read here as introducing Postgres for the ACL
model this phase adds, not migrating `registry.db`/`vectors.db`/
`query_log.db`/`merge_review.db`, none of which the permission-denial exit
criterion touches. Migrating everything would be a much larger, separate
undertaking outside this gate's actual scope.

```bash
PYTHONPATH=src .venv/bin/python -m access.ingest_git --repo data/enterprise_demo --manifest data/enterprise_demo/acl_manifest.json
```

Ingests `data/enterprise_demo/` (a small demo dataset: one public document,
two users' private documents, one document explicitly shared between them)
through the SAME BM25 pipeline every other corpus goes through
(`ingest.pipeline.run_ingest`), but into a **separate index**
(`data/enterprise_tantivy_index/` / `data/enterprise_registry.db`, not
`data/tantivy_index/`) -- keeping this content out of the index the P1/P2
baseline numbers were recorded against, so those stay reproducible. Then
registers each file's access grants from `acl_manifest.json` into the
Postgres-backed `AclStore`. Files not mentioned in the manifest default to
**locked down** (no owner, not public) -- the safe direction to be wrong in,
since indexing a document ahead of knowing its ACL is exactly the leakage
risk this phase exists to prevent. The manifest file itself is excluded
from ACL registration (a real thing caught by running this for real: a
JSON manifest sitting inside the directory it describes otherwise gets
scanned and registered as content).

```bash
PYTHONPATH=src .venv/bin/python -m access.connectors
```

Reports each of the 5 named P5 connectors' status: `git CONNECTED`, and
`sharepoint`/`onedrive`/`outlook`/`teams` all `NOT_CONFIGURED` with the
reason stated (real Microsoft Graph API credentials this project doesn't
have) -- same honest-gate pattern as `ltr.status` for P3.

**Permission-aware search** (`access.permission_filter.PermissionAwareSearch`)
wraps any existing index and filters its results by the requesting user's
access before returning them:

```python
from access.acl_store import AclStore
from access.permission_filter import PermissionAwareSearch
from eval.real_index import RealBM25Index
from config import get_settings

settings = get_settings()
store = AclStore(settings.postgres_dsn)
index = RealBM25Index(settings.enterprise_tantivy_index_dir)
search = PermissionAwareSearch(index, store)
search.search("bob", "Project Falcon", k=10)  # only returns doc_ids bob is authorized for
```

Implementation note: this over-fetches a larger candidate pool from the
underlying index, filters by ACL, then truncates to `k` -- not a true
index-level ACL push-down. Documented limitation: if a user's authorized
set is a small fraction of a large corpus, the fixed fanout might return
fewer than `k` results even though more authorized matches exist further
down the underlying ranking.

### Testing against PostgreSQL

Same pattern as Memgraph: `tests/access/` needs a running PostgreSQL
instance for anything beyond pure logic. `tests/access/conftest.py` probes
connectivity once per session and auto-skips Postgres-dependent tests
(`pytestmark = pytest.mark.requires_postgres`) with a clear reason when
unreachable.

**`tests/access/test_permission_denial.py` is the P5 exit criterion made
concrete:** it runs the real Git connector over the real
`data/enterprise_demo/` into a cleared Postgres + a fresh Tantivy index,
then exercises permission-aware search as three different users (`alice`,
`bob`, `carol`) across 7 scenarios -- cross-user denial both directions, an
unrelated third user, public visibility, explicit-grant visibility, and
denial for a non-grantee.

**These tests wipe the ACL store.** `AclStore.clear()` runs before and
after each test that touches Postgres -- don't point `KE_POSTGRES_DSN` at
an instance holding ACL data you want to keep.

## Running the web crawl (P6)

No extra infrastructure needed -- just real network access (unlike
Memgraph/PostgreSQL, this isn't a Docker service this repo manages):

```bash
PYTHONPATH=src .venv/bin/python -m crawl.pipeline
```

Fetches every URL in `src/crawl/allowlist.py`'s `ALLOWLIST` (checking
robots.txt and applying per-domain rate limiting first), writes each page's
HTML to `data/crawled/`, then runs it through the exact same
`ingest.pipeline.run_ingest` every other corpus uses -- into a **separate**
index (`data/web_tantivy_index/`/`data/web_registry.db`), not the main one,
same reasoning as P5's `enterprise_*` split. Re-running skips URLs already
fetched (`data/crawl_state.db` tracks canonical URLs). `--skip-ingest` runs
the crawl only.

**Merging crawled pages into the live/main index is a deliberate, separate
step -- and it's easy to get wrong.** `ingest.pipeline.run_ingest(corpus_dir,
...)` treats `corpus_dir` as the *complete* contents for that index: any
previously-registered doc not found there gets deleted as stale. Pointing
it at `data/crawled/` (5 files) while targeting the *main* registry (which
tracked 35 files) deleted all 35 -- confirmed live via `eval.run --index
real` suddenly reporting `nDCG@10=0.0000` -- not because of a bug in that
logic, but because of pointing it at the wrong directory for the intent.
**The correct way to merge:** copy the crawled files into `data/corpus/`
itself (the one true corpus dir for the main index), then re-run
`ingest.pipeline` with no `--corpus` override:
```bash
cp data/crawled/*.html data/corpus/
PYTHONPATH=src .venv/bin/python -m ingest.pipeline
```
Also **restart** any running `/search` service afterward if you merge
vectors too -- Tantivy live-reloads on every query (`BM25Index.search()`
calls `.reload()`), but the FAISS vector index is loaded once into process
memory at construction with no reload path, so a running process won't see
newly-added vectors until restarted. Expect the P1/P2 recorded baseline
numbers to shift slightly once crawled content covering the same topics as
judgment-set queries is merged in (measured: nDCG@10 0.8877→0.8749,
recall@20 0.9048→0.8958 after merging these 5 pages) -- real competition
for top-k slots, not a defect.

**The allowlist IS the deliverable** (the roadmap's own framing -- treat it
as such, not a formality, since scope drift here is a legal/ToS exposure
risk). Every entry in `src/crawl/allowlist.py` carries a `reason` and a
`robots_checked` note recording what was actually checked before adding it.
To add a new URL: check its domain's robots.txt directly first (a `curl
https://<domain>/robots.txt` and read it, not an assumption), then add an
`AllowlistEntry` with that evidence recorded, not just the URL.

**Why robots.txt is fetched manually, not via `RobotFileParser.read()`:**
verified directly that Wikipedia returns HTTP 403 for the bare default
User-Agent (`Python-urllib/x.y`) that `read()` uses internally to fetch
robots.txt itself -- and on that 403, it conservatively sets
`disallow_all=True`, meaning every URL on the domain reads as "disallowed"
for a reason that has nothing to do with what robots.txt actually says.
`crawl/robots.py` fetches robots.txt itself with the same declared,
identifiable User-Agent (`crawl/fetcher.py`'s `USER_AGENT`) the real crawl
uses, then feeds the text to the stdlib parser directly.

Test suite (`tests/crawl/`) runs entirely against a local test HTTP server
(`tests/crawl/conftest.py`), not the real allowlist -- proves the mechanism
(robots compliance, rate limiting, canonicalization/dedup, politeness-
budget accounting) without depending on any external site's continued
availability. Always runs, no skip/gate needed.

## Running the optional small-LLM answer layer (P7)

**This is genuinely optional -- every other feature of this project works
without it.** Two things this repo does not manage for you:

1. **`llama-cpp-python` builds from source.** No prebuilt wheel worked
   here; pip's own bundled `cmake` compiles llama.cpp (~5-10 min on
   sensalis-node's 2-core Celeron, needs `gcc`/`g++`, both already present
   on Ubuntu 24.04):
   ```bash
   .venv/bin/pip install llama_cpp_python==0.3.35
   ```
   **This does NOT install on this Windows dev laptop at all** -- the
   sdist's bundled web UI has paths deep enough to hit Windows' MAX_PATH
   limit (`No such file or directory` on a nested `.svelte` file under
   `vendor/llama.cpp/tools/ui/...`). P7 is execution-on-node-only for this
   reason, same as Memgraph/PostgreSQL being services this repo doesn't run
   on the laptop.

2. **The GGUF model itself is not downloaded by this repo.** Tech choice:
   [Qwen2.5-3B-Instruct](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct)
   (Apache 2.0), Q4_K_M quantization (~1.9GB), from a well-known community
   quantizer:
   ```bash
   mkdir -p data/models
   curl -L -o data/models/Qwen2.5-3B-Instruct-Q4_K_M.gguf \
     https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/main/Qwen2.5-3B-Instruct-Q4_K_M.gguf
   ```
   `KE_LLM_MODEL_PATH` (default `data/models/Qwen2.5-3B-Instruct-Q4_K_M.gguf`)
   points the answer layer at it.

```bash
PYTHONPATH=src .venv/bin/python -m answer.pipeline "What is BM25?"
```

Retrieves passages via the same `HybridIndex` P2 built, prompts the model
to answer **extractively, citing the exact chunk id** of every claim in
`[chunk_id]` form, and verifies every citation the model actually produced
traces back to a chunk that was genuinely retrieved -- not a plausible-
looking but hallucinated one. If the model isn't downloaded, this exits
with a clear message rather than crashing, and says P7 is optional.

**CPU inference is genuinely slow on weak hardware -- this is real, not a
bug.** Measured on sensalis-node (2-core Celeron): see
`LOGBOOK_09032026_*.md` for exact per-query timing. This is exactly why the
roadmap marks P7 optional and "no blocking risk" -- the retrieval system
above it (P0-P6) is already the complete, fast product; this layer trades
latency for a natural-language answer on top of it.

**Why citations are checked in code, not just requested in the prompt:** an
instruction telling the model to cite correctly is not a guarantee that it
did. `answer/citation.py`'s `check_citations()` is the actual traceability
mechanism the exit criterion needs -- it extracts every `[...]` bracketed
token from the generated answer and checks it against the set of chunk ids
that were genuinely retrieved for that query, flagging anything else as an
invalid (likely hallucinated) citation.

Tests (`tests/answer/`): `test_citation.py` and `test_prompt.py` are pure
Python, always run. `test_answer_pipeline.py` (real model inference, gated behind
`pytest.mark.requires_llm`, auto-skipped when the package/model aren't
available -- same pattern as Memgraph/PostgreSQL) is real end-to-end but
deliberately kept to 2 test queries given how slow CPU inference is on
this hardware.

**On the actual P7 exit criterion:** `check_citations()` only proves a
citation isn't hallucinated (it points at something genuinely retrieved) --
it can't verify the citation is attached to the *correct* claim when
several retrieved passages contain related content. A real manual
side-by-side review against the actual corpus (3 sampled queries) found
2/3 fully correct and 1/3 with a real misattribution (correct chunk,
wrong claim) -- see `LOGBOOK_09032026_132923.md` for the exact text
comparison. Don't treat "no invalid citations" from the automated check
alone as proof the exit criterion is met; it's a necessary check, not a
sufficient one.

## Running the full test suite (this is the "single documented command")

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q
```

On a machine with Memgraph, PostgreSQL, and the P7 model all available
(e.g. sensalis-node) and real network access: 203 passed, 1 skipped (the
PDF test). Without Memgraph/PostgreSQL/the LLM model (e.g. this repo's dev
laptop, which additionally can't install `llama-cpp-python` at all — see
"Running the optional small-LLM answer layer (P7)"): 151 passed, 53
skipped (29 `tests/kg/` + 21 `tests/access/` + 2 `tests/answer/` cases +
the PDF test) — see "Testing against Memgraph" / "Testing against
PostgreSQL" above. `tests/crawl/` always runs regardless (offline, against
a local test server, not the real allowlist). No prior ingest run needed
for the non-kg/non-access tests —
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
- `tests/kg/test_ner.py` — EntityRuler pattern matches, and the PERSON
  single-token filter against the real false positives it was written to fix.
- `tests/kg/test_relations.py` — clean-SVO extraction, and the cases it
  correctly declines to guess at (3+ entities, no relation verb, no verb).
- `tests/kg/test_resolution.py` — exact-match reuse, fuzzy candidates queued
  not merged, `MergeReviewQueue` CRUD. (No Memgraph needed — pure Python.)
- `tests/kg/test_graph_store.py` *(requires Memgraph)* — upsert/query/count
  against a real Memgraph instance.
- `tests/kg/test_pipeline.py` *(requires Memgraph)* — the full extraction
  pipeline over a small synthetic corpus.
- `tests/kg/test_neighbor_retrieval.py` *(requires Memgraph)* — the P4 exit
  criterion: the fixed 20-entity neighbor-retrieval set, parametrized.
- `tests/access/test_acl_store.py` *(requires PostgreSQL)* — public/owner/
  grant authorization logic, grant/revoke, `authorized_doc_ids` combinations.
- `tests/access/test_git_connector.py` *(requires PostgreSQL)* — manifested
  vs. locked-down-by-default ACL assignment, and the manifest-file exclusion.
- `tests/access/test_permission_filter.py` *(requires PostgreSQL)* — the
  filter-then-truncate logic in isolation, against a fake index.
- `tests/access/test_permission_denial.py` *(requires PostgreSQL)* — the P5
  exit criterion: 7 cross-user leakage scenarios against the real
  `data/enterprise_demo/` dataset.
- `tests/access/test_connectors.py` — connector status is honest (git
  connected, the other 4 not configured with a stated reason). Pure Python,
  always runs.
- `tests/crawl/test_canonicalize.py` — URL canonicalization for dedup.
- `tests/crawl/test_rate_limiter.py` — per-domain politeness timing.
- `tests/crawl/test_robots.py` — robots.txt allow/disallow, against a local
  test server (not the real allowlist).
- `tests/crawl/test_allowlist.py` — structural checks on the allowlist
  itself (every entry has a reason and a robots-review note, no duplicates).
- `tests/crawl/test_crawl_pipeline.py` — the full crawl mechanism end to
  end: fetch, robots-disallow skip, dedup on re-run, politeness-budget
  pass/fail — all against the local test server.
- `tests/answer/test_citation.py` — citation extraction and validation,
  including hallucinated-citation detection. Pure Python, always runs.
- `tests/answer/test_prompt.py` — prompt construction includes the query,
  each passage, its chunk id, and the citation/refusal instructions. Pure
  Python, always runs.
- `tests/answer/test_answer_pipeline.py` *(requires llama-cpp-python + the GGUF
  model)* — real retrieval + real model inference + real citation
  validation, 2 queries.

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
`doc34_kg_relations_demo.txt` and `doc35_kg_more_technologies.txt` (P4) are
hand-written, not generated by a script — short, clean subject-verb-object
sentences added specifically so `kg.relations`' word-order heuristic has
something unambiguous to extract (the rest of the corpus's more
definitional writing style doesn't reliably parse that way — see the P4
logbook for why).

## Reproducing on a fresh Ubuntu 24.04 box (e.g. re-provisioning sensalis-node)

1. `git clone` this repo.
2. Confirm `python3 --version` — Ubuntu 24.04 ships Python 3.12 by default,
   matching sensalis-node's 3.12.3; no version shims needed.
3. `python3 -m venv .venv`, then install torch/torchvision from the CPU wheel
   index FIRST, then `.venv/bin/pip install -r requirements.txt` (see the
   CRITICAL note in `requirements.txt` — skipping this order pulls ~1GB+ of
   unused CUDA packages on Linux). Docling's ML stack itself is a real ~1.8GB
   install — that's expected, not a mistake.
4. `PYTHONPATH=src .venv/bin/python -m pytest -q` — should print `151
   passed, 53 skipped` without Memgraph/PostgreSQL/the P7 model running, or
   start those first (see "Running the knowledge graph pipeline (P4)",
   "Running the access control / Git connector (P5)", and "Running the
   optional small-LLM answer layer (P7)") for `203 passed, 1 skipped`. First
   run needs network once (BGE-Small model download, ~130MB); after that
   it's fully offline except the one PDF-parsing test, which stays
   gated/skipped by default (see "Network dependencies" above).
5. Nothing in this repo hardcodes a path, host, or port — `src/config/__init__.py`
   reads everything from `KE_*` environment variables (or a `.env` file) with
   local-relative defaults, so no config edits should be needed for a basic run.
