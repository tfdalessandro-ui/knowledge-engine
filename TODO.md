# TODO — CPU-First Knowledge Engine

Open items. Created 2026-09-14 (same story as `MASTER.md` — a node-only
copy existed from 2026-09-06, never committed; this replaces it with a
fresh, live-verified version rather than restating the old one). Update
in place going forward; each substantive change should also get a
`LOGBOOK_mmddyyyy_hhmmss.md` entry per house convention (see `LOGBOOK.md`
for the index) — AND get committed/pushed, which the 2026-09-06 copy of
this file never was.

## 1. The four fixes requested 2026-09-06 — re-verified today, live

- [x] **`run_discovery()` audit-trail gap.** Fixed 2026-09-06, still
  correct today. Every call to `discovery.pipeline.run_discovery()` logs
  an `invocations` row (query, caller, pid, timestamp) as its first
  action, regardless of caller — `discovery_provenance.db.invocations`
  has 37 rows as of today (4 from the original 2026-09-06 incident/fix,
  32 from this session's own CX23-parity benchmark, all correctly
  attributed by caller tag). The original untraceable "alpha apples" call
  was never root-caused to a specific process (checked cron, other
  sessions, systemd journal, every running process — inconclusive on
  WHO), but the logging gap itself is closed for good.
- [x] **Crawler re-fetch/TTL.** Fixed 2026-09-06, verified live again
  today: ran `crawl.pipeline` manually just now —
  `fetched=0 rechecked_unchanged=2 rechecked_changed=10 ... elapsed=22.2s`,
  `ingest: scanned=12 added=0 updated=10 unchanged=2`. 10 of 12
  allowlisted URLs were re-fetched (TTL expired) and had a genuinely
  different content hash than last time. `DEFAULT_TTL_DAYS=1.0`, matches
  the daily timer's own cadence.
- [x] **P7 validation batch (Step 5).** The "hung at 104+ min, zero
  progress" state was transient — the batch completed cleanly the same
  day. Confirmed again today: `log/p7_batch_run.log` ends `[20/20] done
  in 1661s ... ALL DONE`, finished 2026-09-07 10:04 UTC. **100% complete
  on the real sample size, which is 20, not 30** — no 30-query batch was
  ever run; that number doesn't correspond to anything in this repo.
- [x] **GA script reproducibility (Step 7) — fully closed 2026-09-14, correcting an earlier wrong claim.**
  An earlier version of this entry said `scripts/ga_chunking.py` was
  "deleted after its one run, unrecoverable" — that was **wrong**, based
  on checking only the GitHub API tree, not the node's actual filesystem.
  In fact it was recreated on 2026-09-06 (see its own docstring and
  `LOGBOOK_09062026_*.md`, Issue 4 of the four-issue fix pass) specifically
  because deleting a script whose cited numeric result feeds the research
  loop's candidate registry was flagged as the wrong convention going
  forward. It existed correctly on sensalis-node the whole time — just,
  like `scripts/auto_tune.py`, never committed to git (zero GitHub history
  for its path, same repo/execution-split symptom). Both, plus
  `scripts/research_loop.py`, `scripts/benchmark_cx23_discovery.py`,
  `AUTO_TUNE_LOG.md`, and `pytest_four_fixes.log`, were pulled from the
  node and committed today as part of item 2 below (the repo/execution
  split fix) — see that item for the full picture of what else this same
  gap had hidden.

## 2. P3 — reranker training

Still blocked, unchanged in nature since it shipped: `ltr.status` today
→ `queries logged: 17, selections logged: 0, threshold: 500, status:
BLOCKED (0/500 interactions)`. This is the roadmap's own disclosed risk
(zero real usage of the system) playing out exactly as predicted, not a
new problem. No action possible until real query traffic with selections
exists.

## 3. P5 — four unconfigured connectors

SharePoint, OneDrive, Outlook, Teams all report `NOT_CONFIGURED` in
`access.connectors` (confirmed in code today, `src/access/connectors.py`)
with an explicit reason: no Microsoft Graph API Azure AD credentials.
Blocked on credentials this project doesn't have, not a code gap.

## 4. P7 — citation accuracy

2/3 on the real exit-criterion wording ("cite the *correct* passages"),
unchanged since 2026-09-08 — one of three sampled answers misattributed a
real citation to the wrong claim among several retrieved passages with
related content. No new validation batch has run since; this number is
not stale re-reporting, it's just the same number because nothing has
re-tested it.

## 5. KG entity/relation count — [x] root-caused and fixed 2026-09-14

Was 0/0 (down from the 2026-09-06 baseline of 215 entity nodes / 9
entity-entity relations). **Root cause**: `run_kg_extraction()` had
exactly one caller anywhere in the codebase — the test fixture in
`tests/kg/test_neighbor_retrieval.py` — and that fixture runs directly
against the *live production* Memgraph instance, `store.clear()`-ing it
both before **and after** every test run. Nothing in production (no cron,
no timer, no ingest hook) ever populated it independently, so the graph
was only ever non-empty for the duration of a `pytest` run, then wiped
clean as teardown. The empty 474-byte snapshot dated 2026-09-06 21:30
lines up almost exactly with the last recorded KG test run that day
(`LOGBOOK_09062026_192407.md`) — that run's teardown is very likely what
zeroed it, and nothing repopulated it after.

**Fix**: added `ke-kg-extract.service` + `.timer` (systemd `--user`, same
pattern as the existing `ke-crawl.timer`), daily **03:15 UTC** (15 min
after the P6 crawl, so same-day corpus changes get picked up), running
`python -m kg.pipeline` against production. Safe to run repeatedly —
`run_kg_extraction()` itself uses `upsert_entity`/`upsert_relation`
(MERGE semantics), it never clears the store; only the test fixture does
that. Ran once manually to populate immediately:
`documents_processed=47 entities_extracted=908 relations_extracted=9
merge_candidates_queued=3`, exit 0. Re-checked live Memgraph with the
label/relation-type-precise query (`MATCH (e:Entity)` /
`MATCH (:Entity)-[r]->(:Entity)`, excluding `Document` nodes and
`MENTIONED_IN` edges, which is what the raw `MATCH (n)` count was missing
before): **215 entity nodes / 9 entity-entity relations — an exact match
to the 2026-09-06 baseline**, confirming the extraction logic and corpus
are stable and nothing was actually lost, just never rewritten.

**Follow-up still open, not yet fixed**: `tests/kg/test_neighbor_
retrieval.py`'s `populated_store` fixture still points at the same live
production `settings.memgraph_uri` and still calls `store.clear()` in
both setup and teardown. **Running this test suite will wipe the
production graph again**, undoing the fix above, until the test gets its
own isolated Memgraph instance (or at minimum stops clearing the
production one). Needs either a separate test Memgraph container/URI in
test config, or a `pytest.fixture` that snapshots+restores instead of
`clear()`ing production.

## 6. Continuous crawler / research-loop / GA-swarm / on-demand-discovery

All four exist and are live (see `MASTER.md` for verified evidence of
each). Nothing further open here beyond what's already itemized above
(GA script's missing git history) and in item 7 below (candidate #1's
pending decision).

- Research-loop candidate #1 (`smaller_chunks_lower_overlap`): still
  `pending`, `decision_date=2026-09-20T15:56:35Z` — 6 days out as of
  today, on track, not overdue. `ke-research-loop.timer` has logged
  `no candidates due for a decision, no rollback triggered` every day
  since 2026-09-07 through today, correctly (nothing has ever been
  promoted, so there's nothing to roll back yet).

## 7. Comparative benchmark (SearXNG / Elasticsearch / Google-Bing)

**Confirmed not started.** No code exists anywhere in this repo for it —
searched for `elasticsearch` (only hits are inside third-party library
internals, none of this project's own code) and any
comparative-benchmark module (none found). It exists only as a mentioned
future step in this doc set, first added 2026-09-06
(`LOGBOOK_09062026_184616.md`).

## 8. Standing process risk — nothing re-checks itself (qualitative assessment, 2026-09-14)

Not a code defect, and not fixed by this entry — recorded because it's the
actual root cause behind items 1, 5, and the `ga_chunking.py`/
`judgments.json` corrections above, and it will keep recurring until
someone owns it deliberately.

**The pattern, seen four separate times in one week**: real work happens
on sensalis-node, is verified once, and is then never re-checked — so a
silent regression sits there indefinitely until someone happens to ask.
KG entity/relation count sat at 0/0 for over a week (test teardown zeroed
production, nothing re-verified it) before this session's status check
caught it. The judgment set grew to 126 queries on the node while git
quietly kept serving a stale 28-query version for over a week too — any
number quoted from "the judgment set" in that window was wrong by 4.4x
and nobody caught it. `scripts/ga_chunking.py` was declared
"unrecoverable, deleted" in an earlier version of this very file, based on
checking GitHub instead of the node itself — wrong, and it stood
uncorrected until re-checked today. MASTER.md/TODO.md/LOGBOOK.md existed
on the node from 2026-09-06 and were never committed until this session
found them by accident while building the root LOGBOOK index.

**Qualitative read on the engine itself, for the record**: P0-P2 (the core
BM25+hybrid retrieval) is genuinely solid — it beat a real, independently
benchmarked OpenSearch baseline on the same corpus today (nDCG@10 0.928 vs
0.865), not just an internal number. P6 and Step 8 are small, correctly
scoped, and working. Everything from P3 onward is an honestly-labeled
prototype, not a shipped capability: P3 has zero real usage (0/500), P5 is
half-built (2 of 6 connectors), P7 is slow (9-11 min/query) and only 2/3
correct on its own exit criterion. None of that is dishonest reporting —
every phase's own docs disclose the gap — but "P0-P7 done" overstates what
a stranger could actually rely on today.

**The git-clone migration (item 2, done 2026-09-14) fixes the delivery
mechanism** that let node-side work go uncommitted. It does NOT fix the
underlying habit of not re-checking things that were verified once. That
needs a deliberate decision — e.g. a periodic status re-check (weekly?),
or a smoke-test cron that asserts KG count > 0 / judgment-set size hasn't
silently shrunk / MASTER.md's own claims still match live state — not
just relying on someone asking again.

## 9. Ready for other topics?

**No — needs code changes, not config.** `src/crawl/allowlist.py` (P6)
and `src/kg/ner.py` (P4's `TECHNOLOGY_TERMS`/`COMPANY_TERMS`/
`PRODUCT_TERMS`) are both hardcoded to this project's own vocabulary.
`src/discovery/pipeline.py` (Step 8) is already topic-agnostic and needs
no changes. A second topic also needs its own P0 judgment set from
scratch before any nDCG@10/MRR/recall@20 number means anything for it —
stated here as an explicit prerequisite, not a nice-to-have.
