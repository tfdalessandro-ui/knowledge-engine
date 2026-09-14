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
- [x]/[ ] **GA script reproducibility (Step 7) — partially closed today.**
  `scripts/ga_chunking.py` (the *original* GA script) was deleted after
  its one run and is **still not recoverable** — checked GitHub directly
  (`api.github.com/.../commits?path=scripts/ga_chunking.py`) — empty
  result, zero history, doesn't exist in the current tree, and no copy of
  it was found on sensalis-node either. That specific script is gone for
  good; only its logged results survive, in
  `LOGBOOK_09032026_161900.md`/`LOGBOOK_09032026_161500.md`.
  Its successor, `scripts/auto_tune.py` (the script actually driving the
  live daily 03:30 UTC tuning cron, real results as recently as
  2026-09-07), had the same problem — zero git history, existed only as
  an uncommitted file on sensalis-node — **pulled into this repo and
  committed today**. Reproducibility is restored going forward from this
  commit; the original `ga_chunking.py` run itself remains
  irreproducible, only its logged numbers are preserved.

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

## 5. KG entity/relation count — real, unresolved regression

Live Memgraph query today: `MATCH (n) RETURN count(n)` → **0**,
`MATCH ()-[r]->() RETURN count(r)` → **0**. Baseline as of 2026-09-06 was
215 entity nodes / 9 entity-entity relations. Snapshot files exist
(`/var/lib/memgraph/snapshots/`, most recent right after an apparent node
restart on 2026-09-10) but are only ~474 bytes each — far too small to
hold 215 entities — including one dated 2026-09-06 21:30, suggesting the
graph was already empty before that restart, not wiped by it. **Not
root-caused** — flagged, not fixed. Needs someone to actually trace why
P4's ingest stopped writing to (or lost) this data.

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

## 8. Ready for other topics?

**No — needs code changes, not config.** `src/crawl/allowlist.py` (P6)
and `src/kg/ner.py` (P4's `TECHNOLOGY_TERMS`/`COMPANY_TERMS`/
`PRODUCT_TERMS`) are both hardcoded to this project's own vocabulary.
`src/discovery/pipeline.py` (Step 8) is already topic-agnostic and needs
no changes. A second topic also needs its own P0 judgment set from
scratch before any nDCG@10/MRR/recall@20 number means anything for it —
stated here as an explicit prerequisite, not a nice-to-have.
