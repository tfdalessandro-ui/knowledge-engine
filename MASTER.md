# MASTER — CPU-First Knowledge Engine

Project-level status summary. Created 2026-09-14, replacing the node-only
copy that existed from 2026-09-06 but was never committed to this repo
(the repo/execution split — git on the laptop, tar-shipped execution on
sensalis-node — let node-side file creation silently skip git). Populated
from real, live-checked repo/log/service state on sensalis-node at
creation time, not carried over from the earlier uncommitted copy's
wording. Sync in place on future changes; don't restate old status words
without re-checking.

## What this is

A retrieval-first search system — BM25 + hybrid search over documents, a
knowledge graph, and an optional small-LLM layer — built to run
acceptably on ordinary CPU cores instead of requiring a GPU. Full detail
in `README.md` and `HELP.md`.

## Infrastructure facts (verified live, 2026-09-14)

- **Production target: sensalis-node itself — not Hetzner CCX23.** Owner
  decision, 2026-09-12 (`LOGBOOK_09122026_125522.md`): the earlier plan to
  provision a separate Hetzner CCX23 VPS for production is **cancelled,
  not deferred**. sensalis-node (dev host throughout the build) is now
  both dev and prod, permanently. `HELP.md`/`README.md` were updated to
  match at the time of that decision but sat uncommitted in the local
  working tree for two days — committed together with this file.
  Practical consequence flagged by the owner at the time: sensalis-node
  has 2 shared CPU cores; any future research-to-production loop /
  GA-swarm tuning / on-demand discovery work competes with live
  query-serving on the same box.
- **Service is live right now**: `knowledge-engine.service` (systemd
  --user, enabled), active since 2026-09-10 05:32:30 UTC — 4 days
  uninterrupted uptime as of this write-up. `/health` → `{"status":"ok"}`.
  `/search?q=okapi+bm25+ranking&k=2` returns real ranked hits (BM25+vector
  RRF) from the live index, verified this session.
- **Repo/execution split**: git repo on the laptop, pushed to
  `https://github.com/tfdalessandro-ui/knowledge-engine`. Execution on
  sensalis-node is shipped via `tar` over SSH, **not a git clone** —
  `git log` on sensalis-node's checkout returns `fatal: not a git
  repository`. This is the documented normal pattern (see `HELP.md`), but
  it has a real, repeatedly-observed failure mode: files created directly
  on the node (docs, scripts) don't automatically flow back into git.
  Confirmed casualties as of this write-up: `scripts/ga_chunking.py`
  (deleted after its one run, never recommitted — see TODO.md item 4),
  `scripts/auto_tune.py` (live on the node, zero git history), and until
  today, 20 of 31 `LOGBOOK_*.md` entries plus this file, `TODO.md`, and
  the git-side `LOGBOOK.md` index itself.

## Phase status (P0-P7, as of the 2026-09-08 GitHub HEAD `60d2187`)

- **P0** (foundations/eval harness): done. nDCG@10/MRR/recall@20 harness,
  126-pair judgment set (grown from the original 79 across several
  sessions).
- **P1** (BM25 MVP): done. Docling parsers + Tantivy, incremental
  re-index proven live.
- **P2** (hybrid retrieval): done. BGE-Small + FAISS/HNSW + RRF, weighted
  score fusion deployed after GA tuning (rrf_k=1, cross-validated) beat
  plain RRF.
- **P3** (usage capture + LTR): infra done, reranker training still
  **honestly blocked**. Live check today: `ltr.status` →
  `queries logged: 17, selections logged: 0, threshold: 500,
  status: BLOCKED (0/500 interactions)`. Zero real usage of this system
  since it shipped — not a bug, the roadmap's own named risk playing out.
- **P4** (NER + knowledge graph): built and previously verified
  (100% manual spot-check precision, 53/53), but **the live Memgraph
  instance currently holds 0 entity nodes / 0 relations** against a
  2026-09-06 baseline of 215/9 — a real, unresolved regression, not
  re-derived here (see TODO.md item 5 for what's known and not known
  about why).
- **P5** (enterprise connectors + ACLs, hard gate): ACL core + Git
  connector done and verified. SharePoint/OneDrive/Outlook/Teams remain
  **honestly not built** — `access.connectors` reports all four
  `NOT_CONFIGURED` with an explicit reason (no Microsoft Graph API Azure
  AD credentials), confirmed still true today.
- **P6** (web crawl): done, live, running daily. `ke-crawl.timer`
  (03:00 UTC) re-fetches the 12-URL allowlist with real TTL/re-fetch
  logic — verified live today (`rechecked_changed=10` on this session's
  own manual run).
- **P7** (optional small-LLM layer): built, **honest partial result,
  unchanged since 2026-09-08**. The 20-query citation-validation batch
  is 20/20 complete (`ALL DONE`, finished 2026-09-07 10:04 UTC — no
  30-query batch was ever run, despite that number appearing in some
  status-check templates). Citation accuracy on manual side-by-side
  check: 2/3 sampled answers correctly cited, one misattributed a real
  citation to the wrong claim. Latency 543-681s/query on this 2-core
  Celeron — the concrete reason this phase is optional.

## Work beyond P0-P7 (Build Kickoff plan, approved 2026-09-06)

All of the following are live, running on their own schedule, verified
today:

- **Continuous crawler** (Step 1) — `ke-crawl.timer`, daily 03:00 UTC.
  Real re-fetch/TTL (`DEFAULT_TTL_DAYS=1.0`), not just a timer firing.
- **Research-to-production loop** (Step 2) — `ke-research-crawl.timer`
  (04:00) + `ke-research-loop.timer` (04:30), both daily. One candidate
  registered (`smaller_chunks_lower_overlap`, 0.9091→0.9177 nDCG@10),
  `status=pending`, `decision_date=2026-09-20` — 6 days out as of this
  write-up, not yet due. No rollback ever triggered (nothing has been
  promoted yet to roll back).
- **Usage capture** (Step 3) — wired, running, feeding P3 (see above);
  not "done" in the sense of unblocking anything, it's a running count.
- **GA/swarm manual-trigger tuning** (Step 4/7) — `scripts/auto_tune.py`,
  cron daily 03:30 UTC. Last real tuning run 2026-09-07:
  `Held-out: champion=+4.56% deployed=+4.38% -> not deployed`. Every run
  since has logged `No change detected — skipped` (no corpus/judgment
  change to retune against) — expected, not a fault. **The script itself
  has zero git history** (see TODO.md item 4).
- **On-demand keyword discovery** (Step 8) — `discovery.pipeline.
  run_discovery()`, triggered by `/search` on sparse results, or callable
  directly (used for the CX23 benchmark below). Full audit trail via
  `discovery_provenance.db.invocations` (37 rows as of today, logs every
  call regardless of caller — the 2026-09-06 fix).
- **Comparative benchmark vs. SearXNG/Elasticsearch/Google-Bing**
  (Step 9) — **not started**. No code for it exists anywhere in the repo;
  only mentioned as a planned item in this doc set. Confirmed by search:
  no `elasticsearch` references outside third-party library internals,
  no comparative-benchmark module.
- **CX23 doc-discovery parity benchmark** (2026-09-13/14, ad hoc, not
  part of the Step 1-9 plan) — Step 8's discovery pipeline was fed the
  same 30 keyword queries Sensalis' own `doc_source_discovery.py` issues
  on CX23. Result: 90/90 documents fetched here vs. 0 new candidates on
  CX23 that day (root-caused separately to Serper credit exhaustion on
  CX23, now resolved — unrelated to this project's own code). Full
  writeup: `LOGBOOK_09142026_053349.md`.

## Is this ready for other topics?

**No, not without code changes.** P6's allowlist (`src/crawl/allowlist.py`)
and P4's entity term lists (`src/kg/ner.py`) are both hardcoded Python
literals scoped to this project's own subject matter (search/ranking) —
swapping topics means editing source, not flipping a config value. Step 8
discovery (`src/discovery/pipeline.py`) IS topic-agnostic (generic
search-API + robots + blocklist, no hardcoded terms) and would work
unmodified on a new topic. A second topic also needs its own P0 judgment
set before "better/worse" numbers mean anything for it — the current
126-pair set and every nDCG@10/MRR/recall@20 baseline are scoped to this
corpus only.
