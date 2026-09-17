# TODO — CPU-First Knowledge Engine

Open items. Created 2026-09-06 (did not exist before this entry) — populated
from the real repo/log state at creation time, not a placeholder. Update in
place going forward; each substantive change should also get a
`LOGBOOK_mmddyyyy_hhmmss.md` entry per house convention (see `LOGBOOK.md`
for the index).

## Build Kickoff plan (approved 2026-09-06) — Steps 1-9

Status pulled live from the repo/logs at the time of this entry
(2026-09-06, ~18:45 CEST / ~16:45 UTC) — not restated from earlier
in-chat status words.

### Step 1 — Continuous crawler
**Done, live.** `ke-crawl.timer` active, next fire 2026-09-07 03:00 UTC.
Real, disclosed limitation: `crawl.pipeline` has no re-fetch/TTL
mechanism — it will report `fetched=0` on every run indefinitely unless
the allowlist itself grows. See `LOGBOOK_09062026_162250.md` and earlier
Step-1 entries for the full evidence.

### Step 2 — Research-to-production loop
**Done, live, one candidate pending a real decision.** `research/`
package built (separate crawl target from P6, candidate registry,
mechanical decide/rollback logic). Candidate #1
(`smaller_chunks_lower_overlap`, Step 7's chunking discovery,
0.9091→0.9177 nDCG@10) is **`pending`**, real `decision_date =
2026-09-20T15:56:35Z` (confirmed live in `data/research_candidates.db`
at the time of this entry — not yet due). `ke-research-crawl.timer` /
`ke-research-loop.timer` both active, next fires 2026-09-07 04:00/04:30
UTC. See `LOGBOOK_09062026_160250.md`.

### Step 3 — Usage capture
**Confirmed wired, not "done" in the sense of unblocking P3** — this
step doesn't finish, it's a running count. As of this entry:
**14 queries logged, 0 selections logged** in `data/query_log.db`
(checked live, not carried over from an earlier number in this session —
was 11 a few hours earlier the same day). Still far from the 500-selection
threshold `ltr.train` requires.

### Step 4 — P5 credentials
**Confirmed blocked**, unchanged: `access.connectors` reports all four
of sharepoint/onedrive/outlook/teams as `NOT_CONFIGURED` (no Azure AD app
registration/tenant access exists for this project). No workaround
attempted. Revisit only if real credentials become available.

### Step 5 — P7 20-query citation validation set
**IN PROGRESS, running much slower than expected — flagged, not hidden.**
`p7_batch_run.py` (PID 2359923) has been running **73+ minutes** as of
this entry and has not yet completed even query 1 of 20 (historical
per-query baseline on this hardware: ~9-11 minutes). Checked for
swapping/memory thrashing earlier in this session — none found (0 swap
used, plenty of free RAM) — so this is judged "slow, not crashed," but
the slowdown is now large enough (originally 5x baseline, now more like
7-8x) that it warrants closer attention if it doesn't produce a first
result soon. A scheduled follow-up check is queued (task
`check-p7-batch-progress`, fires ~18:42 CEST 2026-09-06). **No citation-
correctness numbers exist yet** — the original 3-query result (2/3
correct) is still the only real data point until this batch produces
something.

### Step 6 — KG relation-extraction expansion
**Done, real finding, no code change made (as instructed).** Live graph
(as of the last `kg.pipeline` run, 2026-09-06): 215 entities, 9
entity-to-entity relations — entities grew 3.5x from the original
62-entity baseline, relations stayed at exactly 9. Assessment: the
rule-based pattern extractor only fires on the two original hand-written
clean-SVO documents; it produced zero relations from any of the newer
prose-style content (7 crawled Wikipedia pages, other corpus growth).
Needs more/broader patterns or a different approach for prose text —
not "expected at current scale." See `LOGBOOK_09062026_160250.md`.

### Step 7 — GA/swarm tuning, manual trigger
**Done, standalone, not yet deployed.** Real GA search over
`ingest.chunking.chunk_text`'s min_tokens/max_tokens/overlap_ratio found
+0.94% nDCG@10 on the P0/P1 BM25-only harness (0.9091 → 0.9177, chunk
params 250/400/0.15 → 142/340/0.007). Not folded into production —
became Step 2's candidate #1 instead, now going through the mechanical
decide-at-day-14 lifecycle rather than being applied directly.

### Step 8 — On-demand keyword discovery
**Done, live-verified end to end.** `discovery/` package built (SearXNG
client, StevenBlack/hosts blocklist, robots.txt check, hard cap of 3
URLs/trigger, provenance tagging, separate index namespace). Live run
confirmed: a genuinely off-topic query triggered discovery, all
guardrails visibly executed, 3 documents fetched/tagged/indexed, found
again via `discovery.search_discovered` with correct provenance. One
real calibration correction made and disclosed along the way (the
sparsity-detection threshold needed two rounds of live testing before it
actually worked — see `LOGBOOK_09062026_162250.md` for the full
before/after). No LLM/GPU anywhere in this step, confirmed by code
review of every module in the chain.

### Step 9 — Comparative benchmark (added 2026-09-06, not started)

Benchmark this engine against three targets, two separate dimensions.
**Not blocking Steps 1-8; independent, run once the engine has
stabilized.**

**Dimension A — Relevance quality.** Same P0 judgment set
(`data/judgments/judgments.json`, currently 126 queries / 246 pairs)
scored via nDCG@10/MRR/recall@20 against:
1. This engine (already measured continuously — current live config:
   weighted fusion, alpha=0.535, ~+2.66% over BM25-only on the last
   full-set measurement, though the judgment set has grown since).
2. SearXNG — **already running on this node** (127.0.0.1:8888, reused
   from an unrelated project, confirmed live and already integrated as
   Step 8's search backend) — no new self-hosting needed, unlike the
   plan's default assumption. Needs a harness that queries it and scores
   results against the same judgment set (not yet built).
3. Elasticsearch/OpenSearch — needs a self-hosted instance. **Not yet
   provisioned on this node** (not found in the running-process/Docker
   audit done for Step 8). Provisioning + indexing the same 47-doc corpus
   is a real prerequisite, not started.
4. Google/Bing API — **flagged in advance as likely blocked**, same
   category as Step 4's Microsoft Graph blocker: no API credentials
   exist for this project. Confirm and report plainly when this step is
   actually attempted; don't invent a workaround if blocked.

**Dimension B — Speed & resource efficiency.** p50/p95 latency, CPU
utilization, peak RSS, same query set, on hardware comparable to the
CCX23 production target (4 dedicated vCPU / 16GB, Helsinki) — **this
project's actual dev/execution hardware, sensalis-node, is a 2-core
Celeron laptop, NOT comparable to CCX23** (already a known,
previously-disclosed mismatch throughout this project's history, e.g.
P2's node-vs-laptop cross-platform variance findings). Any Step 9
resource-efficiency numbers measured on sensalis-node must state this
mismatch explicitly, not present them as CCX23-equivalent. If a real
CCX23 instance is provisioned for this measurement, note that instead.

**Exit criteria**: real numbers for both dimensions, per target,
including for any target that couldn't be completed — stated as a
disclosed limitation (e.g. "Google/Bing: blocked, no credentials", not
silently omitted from the results table).

**Status: not started.** No benchmark harness exists yet, no
Elasticsearch/OpenSearch instance exists, API credential status for
Google/Bing not yet checked.
