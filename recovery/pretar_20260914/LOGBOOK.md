# LOGBOOK — Root Index

Running index of every timestamped `LOGBOOK_mmddyyyy_hhmmss.md` entry,
newest first. This file is an index only — it never contains the actual
findings, only a pointer and the entry's own title line (pulled directly
from each file, not paraphrased). The timestamped files themselves are
append-only and never overwritten in place; this index is updated by
appending a new row at the top each time a new one is created.

Created 2026-09-06, backfilled with all 24 entries that existed at
creation time (2026-09-02 through 2026-09-06).

| Logbook file | Title |
|---|---|
| `LOGBOOK_09142026_053349.md` | CX23 doc-discovery parity benchmark: Step 8 fed the same 30 queries as Sensalis crawler, 90/90 fetched, CX23 side found stale 14 days |
| `LOGBOOK_09062026_162250.md` | Build Kickoff Step 8: on-demand keyword discovery, built and verified live (with a real threshold-calibration correction along the way) |
| `LOGBOOK_09062026_160250.md` | Build Kickoff (8-step plan): Steps 1, 3, 4, 6, 7, 2 done with real evidence; Step 5 running; Step 8 next |
| `LOGBOOK_09062026_112233.md` | Judgment set grown again (106→126 queries); status check on the recurring auto-tune first |
| `LOGBOOK_09062026_092300.md` | KE_AUTO_TUNE first-scheduled-runs check (2026-09-06 09:23 UTC) |
| `LOGBOOK_09042026_112500.md` | Recurring auto-tune built, verified live, scheduled; a note on how it got verified |
| `LOGBOOK_09042026_103825.md` | auto_tune.py run (2026-09-04 10:38 UTC) |
| `LOGBOOK_09042026_060353.md` | Weighted score fusion beats RRF; deployed. Plus: fork points for future exploration |
| `LOGBOOK_09042026_055006.md` | Round-2 CV validates rrf_k=1; deployed to production |
| `LOGBOOK_09042026_050500.md` | Judgment set grown to 100+ queries per explicit user request; ceiling raised; P2 still fails, unchanged sign |
| `LOGBOOK_09032026_161900.md` | GA parameter tuning for P2 confirmed to overfit; not deployed |
| `LOGBOOK_09032026_161500.md` | Session paused for unplanned node power-off; GA overfitting test mid-run |
| `LOGBOOK_09032026_155830.md` | Grew the judgment set to fix P2; it didn't, and revealed something worse |
| `LOGBOOK_09032026_152832.md` | P2 exit criterion FAILS post-merge; root-caused a pre-existing FAISS/registry orphan gap |
| `LOGBOOK_09032026_142903.md` | Deploying as a live service, and a real merge-ingest mistake |
| `LOGBOOK_09032026_140900.md` | Crawler scheduled, allowlist grown, merge paused mid-run (session stop) |
| `LOGBOOK_09032026_134309.md` | Independent live-status re-check, open items restated, docs sync |
| `LOGBOOK_09032026_132923.md` | P7: Optional Small-LLM Answer Layer |
| `LOGBOOK_09032026_082933.md` | P6: Web Crawl Expansion (allowlisted, not general crawling) |
| `LOGBOOK_09032026_080855.md` | P5: Enterprise Connectors & Access Control (ACL core + Git only) |
| `LOGBOOK_09032026_074714.md` | P4: Entity Extraction & Knowledge Graph v1 |
| `LOGBOOK_09032026_002053.md` | P3: Usage Capture & Learning-to-Rank (infra only, training gated) |
| `LOGBOOK_09032026_000504.md` | P2: Hybrid Retrieval (BGE-Small + FAISS/HNSW + RRF) |
| `LOGBOOK_09022026_214005.md` | P0/P1 Live Verification (re-run before starting P2) |
| `LOGBOOK_09022026_175124.md` | P1: Ingestion & BM25 MVP |
| `LOGBOOK_09022026_173751.md` | P0 Kickoff: CPU-First Knowledge Engine Foundations |

## New entry for this change

`LOGBOOK_09062026_184616.md` — documents the creation of `TODO.md`,
`MASTER.md`, and this file (none existed before), and the addition of
Step 9 (comparative benchmark) to the Build Kickoff plan.
