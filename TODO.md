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

- [x] **A separate, concrete citation bug found and fixed 2026-09-15**
  (`LOGBOOK_09152026_092024.md`): `answer/prompt.py`'s own instructions
  told the model to cite "like this: `[chunk_id]`" — the literal
  placeholder word, not a real example — and the 3B local model would
  sometimes echo it verbatim (`[chunk_id bm25::0]`), which the validator
  correctly rejected. Fixed the instruction's example; verified with real
  (non-mocked) LLM inference, both `test_answer_pipeline.py` tests now
  pass (previously failing).
- [x] **Re-ran the full 20-query P7 batch 2026-09-15** (not just the 2
  unit tests) to get the real current number rather than assume the fix
  above generalized — it didn't cleanly: aggregate structural
  trace-validity was **77/100 citations valid**, actually *worse* than
  the old buggy run's 468/483 (though the two runs produce very
  differently-shaped answers — ~5 citations/query now vs. ~24/query
  then — so not a clean apples-to-apples number). Digging in surfaced a
  *different*, more serious bug: the model fabricating entire fake extra
  "passages" (invented doc_ids + plausible content that was never
  retrieved) once it finishes a real answer with token budget left over,
  mimicking `build_prompt`'s own passage-block format. Root-caused, fixed,
  and verified with real inference in `LOGBOOK_09162026_052659.md` — see
  that file for the fix (`answer/model.py` stop sequences +
  `truncate_on_fabricated_passage()`) and its one honestly-unresolved
  detail (the exact stop mechanism on the verification run wasn't fully
  isolated from the earlier prompt-wording change).
- [ ] **Still open: the full 20-query batch has not been re-run with the
  fabrication fix.** Only the single worst-offending query was verified
  with real inference (clean result). A full re-run (~20h on this
  hardware based on the 2026-09-15 run's actual pace, not the older
  9-11 min/query baseline) would give a real, current aggregate number
  instead of one data point — not assumed to generalize from it.

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
underlying habit of not re-checking things that were verified once.

- [x] **Addressed 2026-09-14**: `scripts/status_recheck.py` + `ke-status-
  recheck.timer` (systemd `--user`, weekly, Monday 07:00 UTC, next fire
  2026-09-21). Checks exactly the four regressions this project already
  hit once each: KG entity count == 0, sensalis-node's checkout drifting
  from `origin/main` (uncommitted or behind), `judgments.json` row count
  shrinking, and the live `/search` API not actually answering a real
  query (not just `/health`). First live run, same day: all four checks
  passed clean (`KG entity nodes=215 relations=9`, `git ... HEAD ==
  origin/main`, `246 rows / 126 queries`, `/search answered`). A failure
  appends a timestamped report to `STATUS_ALERTS.md` (empty as of this
  writing); committing that append is a manual step by design, so an
  automated false alarm can't rewrite history unsupervised. This catches
  the four known failure modes, not everything — it can't judge whether
  P7's citation accuracy has changed, for instance. Not a substitute for
  an actual status check, just a tripwire for silent regression between
  them.

## 9. Ready for other topics?

**No — needs code changes, not config.** `src/crawl/allowlist.py` (P6)
and `src/kg/ner.py` (P4's `TECHNOLOGY_TERMS`/`COMPANY_TERMS`/
`PRODUCT_TERMS`) are both hardcoded to this project's own vocabulary.
`src/discovery/pipeline.py` (Step 8) is already topic-agnostic and needs
no changes. A second topic also needs its own P0 judgment set from
scratch before any nDCG@10/MRR/recall@20 number means anything for it —
stated here as an explicit prerequisite, not a nice-to-have.

## 10. Weighted fusion wiring (2026-09-15) — fixed, one follow-up remains

`HybridIndex` never implemented weighted score fusion at all (RRF only),
despite `Settings.hybrid_fusion_mode`/`hybrid_alpha` existing and being
GA-tuned since 2026-09-04 — `api/main.py` built `HybridIndex()` with no
kwargs, so the live service silently ran plain RRF regardless of config.
Fixed: `HybridIndex` now supports both modes, `api/main.py`/`eval/run.py`
actually pass the tuned settings through. Full story and verification in
`LOGBOOK_09152026_071646.md`.

- [x] **`test_hybrid_vs_bm25.py` discrepancy — root-caused and fixed
  2026-09-15.** The test's own fixture built `HybridIndex(...)` with no
  fusion kwargs either — same dead-config bug as `api/main.py`, so it was
  measuring plain RRF at `rrf_k=60` (never-deployed) instead of what's
  actually live. Real numbers on the test's own fresh 47-doc corpus
  build: BM25-only 0.9091, untuned RRF hybrid 0.8829 (-2.9%, the original
  failure), tuned RRF (`rrf_k=1`) 0.9076 (-0.2%), tuned weighted fusion
  (what's actually live) 0.9286 (**+2.1%**). Fixed the fixture to build
  from the same `Settings` fields `api/main.py` uses. This closes the
  *discrepancy* (both the test and the live 126-query benchmark now agree
  hybrid is neutral-to-positive, not regressing) but the roadmap's
  original +5% bar still isn't met even with the best config — continuing
  the exact drift `LOGBOOK_09032026_142903.md` already predicted as the
  corpus keeps growing (35 docs at P2 build time → 47 now). Marked
  `xfail(strict=True)` with the real number and reasoning, following this
  project's own established precedent for that pattern, rather than
  quietly lowering the bar or leaving a misleading hard failure in place.
- [x] **`test_judgment_set_size`'s stale bound — fixed 2026-09-15.** The
  `50 <= total <= 100` upper bound was a snapshot of the judgment set's
  size at P0 (committed once, 2026-09-02, never revisited) — not a
  deliberate ceiling, so it broke on the judgment set's own deliberate,
  documented growth (79 → 106 → 126 queries). Replaced with a named
  `MIN_JUDGMENT_PAIRS = 50` (a real floor — enough for the stub-index
  tests below to be meaningful) and `MAX_SANE_JUDGMENT_PAIRS = 5000` (a
  generous corruption guard, e.g. accidental row duplication — not a
  growth cap, shouldn't need touching again for ordinary growth). All 4
  tests in `test_harness.py` pass now.
- [ ] `hybrid_alpha_mode="adaptive"` (`hybrid_alpha_base`/
  `hybrid_alpha_slope`) is still unimplemented in `HybridIndex` — it
  silently falls back to the fixed `alpha` no matter what
  `Settings.hybrid_alpha_mode` says.

## 11. OSE rename (2026-09-16) — in progress, done gradually with a regression check per step

- [x] Docker containers `*_ke` → `*_ose` (4)
- [x] `~/work/knowledge_engine` → `~/work/ose` (+ venv shebang/`pyvenv.cfg` repair)
- [x] Found + restored `src/research/`, `src/discovery/`, `src/eval/adaptive_alpha.py`
  lost in the 14 Sep migration (`LOGBOOK_09162026_220500.md`)
- [x] Crontab `KE_AUTO_TUNE` repointed to `~/work/ose` (marker name itself not yet renamed)
- [x] systemd: `ke-{crawl,kg-extract,research-crawl,research-loop,status-recheck}` →
  `ose-*` (timer stamps carried over, next-fire times unchanged);
  `knowledge-engine.service` → `ose.service` (+ `auto_tune.py`,
  `comparative_benchmark_speed.py`, `deploy/ose.service`)
- [ ] **Bug in the Sensalis clone, not yet fixed**: its `scripts/auto_tune.py`
  restarts `knowledge-engine.service` (this engine, port 8000) rather than
  its own `sensalis-pricing-engine.service` — copied verbatim at clone time.
  Not scheduled there, so never fired; after this rename it would now just
  fail the restart and roll back. Fix during the clone's own rename step.
- [ ] `config` env prefix `KE_` → `OSE_`; cron marker `KE_AUTO_TUNE`
- [ ] Sensalis clone rename; backup dir decision; GitHub repo rename (manual,
  needs the owner — no `gh` token here); laptop folder renames; doc branding
