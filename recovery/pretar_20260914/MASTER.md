# MASTER — CPU-First Knowledge Engine

Project-level status summary. Created 2026-09-06 (did not exist before
this entry) — populated from real, live-checked repo/log state at
creation time. Sync in place on future changes; don't restate old status
words without re-checking.

## What this is

A retrieval-first search system — BM25 + hybrid search over documents, a
knowledge graph, and an optional small-LLM layer — built to run
acceptably on ordinary CPU cores instead of requiring a GPU. Full detail
in `README.md` and `HELP.md`.

## Infrastructure facts (verified at creation time, not assumed)

- **Production target**: Hetzner CCX23, Helsinki (4 dedicated vCPU,
  16GB RAM) — **not yet provisioned**; this remains a target, not a live
  deployment, as of this entry.
- **Development/execution host**: sensalis-node
  (`sensalis@192.168.178.65`, reachable off-LAN via
  `ssh -i ~/.ssh/id_ed25519 -J root@157.90.229.194 -p 2222
  sensalis@localhost`) — a 2-core Celeron laptop, genuinely NOT
  comparable to CCX23's hardware. This gap is load-bearing for
  interpreting every performance number in this project (see Step 9's
  Dimension B in `TODO.md`) — do not present sensalis-node timings as
  CCX23-equivalent without saying so.
- **Repo/execution split**: the git repository lives on the operator's
  laptop, pushed to `https://github.com/tfdalessandro-ui/knowledge-engine`.
  Execution on sensalis-node is shipped via `tar` over SSH, **NOT a git
  clone** — confirmed live at the time of this entry: `git log` on
  sensalis-node's checkout returns `fatal: not a git repository`. This is
  the project's normal, documented operating pattern (see `HELP.md`'s
  repo/execution split section), not a defect — but it means this file
  cannot report git commit history for the node's own state; commit
  history, if needed, must come from the laptop's checkout or GitHub
  directly, not from sensalis-node.
- **Step 8's no-LLM/no-GPU constraint**: confirmed still accurate by
  code review at the time of this entry — `discovery/search.py`,
  `discovery/blocklist.py`, `discovery/pipeline.py` contain no LLM calls;
  candidate filtering is pure robots.txt + domain-blocklist rule logic;
  content extraction reuses `crawl.fetcher.fetch_url` (plain HTTP GET)
  and `ingest.pipeline`'s existing P1/P2 parsing+embedding stack. P7's
  optional LLM layer is untouched and separate.
- **Self-hosted services already running on sensalis-node** (reused, not
  deployed fresh for this project): SearXNG (127.0.0.1:8888, Step 8's
  search backend, also Step 9's Dimension-A target #2), Memgraph
  (127.0.0.1:7687, P4's knowledge graph), PostgreSQL (127.0.0.1:5433,
  P5's ACL store).

## Phase status (P0-P7) — as of this entry

Pulled from `README.md`'s own live-verified status line, cross-checked
against today's (2026-09-06) live checks, not restated from memory:

| Phase | Status |
|---|---|
| P0 (eval harness) | Done |
| P1 (BM25 MVP) | Done |
| P2 (hybrid retrieval) | Exit criterion (+5% nDCG@10) **still NOT met** — current live measurement +2.66% (weighted fusion, alpha=0.535), up from a low of -1.68% across a multi-attempt investigation (judgment-set growth x2, RRF tuning, weighted-fusion redesign). Judgment set has grown again since that last full-set measurement (106→126 queries as of 2026-09-06) — the +2.66% number has NOT been re-measured against the current 126-query set as of this entry. |
| P3 (usage capture + LTR) | Infra done, training blocked — **14 queries / 0 selections** logged as of this entry (see TODO.md Step 3), nowhere close to the 500-interaction gate. |
| P4 (KG v1) | Infra done; **relation-extraction found genuinely limited at current scale** (215 entities / 9 relations, frozen — see TODO.md Step 6) — not silently marked "done" without that caveat. |
| P5 (enterprise connectors, hard gate) | ACL core + Git connector done and verified; SharePoint/OneDrive/Outlook/Teams **confirmed blocked**, no Azure AD credentials (see TODO.md Step 4). |
| P6 (web crawl) | Done; now recurring via `ke-crawl.timer` (Step 1) rather than a one-time batch — real disclosed limitation: no re-fetch/TTL, so daily runs report `fetched=0` indefinitely absent allowlist growth. |
| P7 (optional small-LLM layer) | Built; citation-accuracy validation set expansion **in progress, running far slower than expected** (Step 5, 73+ min on query 1 of 20 as of this entry) — no new numbers yet beyond the original 3-query (2/3 correct) result. |

## Build Kickoff plan — Steps 1-9

Full per-step detail lives in `TODO.md`, kept in sync with this file.
One-line status summary as of this entry:

1. Continuous crawler — done, live, disclosed no-TTL limitation.
2. Research-to-production loop — done, live; candidate #1 pending a real
   decision on 2026-09-20.
3. Usage capture — confirmed wired; running count (14/0 as of this
   entry), not something that "finishes."
4. P5 credentials — confirmed blocked, stopped there per instruction.
5. P7 20-query validation set — in progress, real slowdown flagged (not
   hidden), no results yet.
6. KG relation-extraction expansion — done; real limitation found and
   assessed, no code change forced.
7. GA/swarm tuning, manual trigger — done standalone (+0.94% nDCG@10 on
   chunking params); became Step 2's candidate #1 rather than being
   deployed directly.
8. On-demand keyword discovery — done, live-verified end to end,
   including a disclosed live calibration correction.
9. Comparative benchmark — **added 2026-09-06, not started.** See
   `TODO.md` for the full two-dimension design (relevance vs.
   SearXNG/Elasticsearch/Google-Bing, and speed/resource efficiency on
   CCX23-comparable hardware). Real, already-known blockers/gaps flagged
   in advance: Elasticsearch/OpenSearch not provisioned, Google/Bing API
   credentials not confirmed to exist, sensalis-node is not
   CCX23-comparable hardware.

## Key decisions on record

- P2's regression (see phase table above) has been worked on repeatedly
  across multiple sessions with two disclosed failed fix attempts
  (judgment-set growth alone, an early GA round confirmed to overfit)
  before the currently-deployed weighted-fusion mechanism. Full history
  in the `LOGBOOK_0904*` through `LOGBOOK_0906*` sequence — see
  `LOGBOOK.md` for the index.
- Step 7's chunking discovery was deliberately NOT deployed directly to
  production; it was registered as Step 2's research-loop candidate #1
  instead, specifically to exercise the new mechanical
  decide-at-day-14/rollback machinery on a real result rather than a
  synthetic one.
- Step 8's on-demand discovery keeps discovered content in a fully
  separate index/registry namespace from both the main P1/P2 index and
  P6's crawled content — never silently merged, by design.
