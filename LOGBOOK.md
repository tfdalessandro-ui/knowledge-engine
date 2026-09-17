# LOGBOOK — Root Index

Running index of every timestamped `LOGBOOK_mmddyyyy_hhmmss.md` entry,
newest first. This file is an index only — it never contains the actual
findings, only a pointer and the entry's own title line (pulled directly
from each file, not paraphrased).

Created 2026-09-14. All 31 entries that existed at creation time were
already on disk in the sensalis-node execution copy (created between
2026-09-02 and 2026-09-14) but most had never been committed to this git
repo — the repo/execution split (git on the laptop, tar-shipped execution
on sensalis-node, not a git clone) meant node-side files routinely never
made it back. Pulled all 31 files from the node and committed them
together with this index so the git history actually matches what
happened. See `LOGBOOK_09142026_053349.md` for one concrete example of
this same gap (`scripts/auto_tune.py`, `scripts/ga_chunking.py`) that is
still open as of this index's creation.

| Logbook file | Title |
|---|---|
| `LOGBOOK_09172026_000500.md` | Logbook — OSE rename: laptop folders renamed; laptop venv repaired (including damage I caused) |
| `LOGBOOK_09162026_233500.md` | Logbook — Instance sync: original ↔ instances, built and verified live |
| `LOGBOOK_09162026_233000.md` | Logbook — OSE rename: Sensalis clone → `ose_sensalis` / `ose-sensalis.service` |
| `LOGBOOK_09162026_224500.md` | Logbook — OSE rename: config env prefix KE_ → OSE_ |
| `LOGBOOK_09162026_221500.md` | Logbook — OSE rename: systemd units renamed one at a time, each with a regression check |
| `LOGBOOK_09162026_220500.md` | Logbook — Three packages silently lost in the 14 Sep migration; found by the OSE-rename regression check, restored |
| `LOGBOOK_09162026_052659.md` | Logbook — P7 fabricated-passage bug: root-caused and fixed, real inference verified |
| `LOGBOOK_09152026_092024.md` | Logbook — P7 citation-parsing test failure root-caused: the prompt's own example was the bug |
| `LOGBOOK_09152026_071646.md` | Logbook — Weighted fusion was dead config; recovered a lost module, wired it up, fixed a real Sensalis ranking bug |
| `LOGBOOK_09142026_053349.md` | Logbook — CX23 doc-discovery parity benchmark (Step 8) |
| `LOGBOOK_09122026_125522.md` | Logbook — production target decision: sensalis-node replaces Hetzner CCX23 |
| `LOGBOOK_09082026_113500.md` | Logbook — P7 20-query citation-validation batch: quality review |
| `LOGBOOK_09072026_033003.md` | Logbook — auto_tune.py run (2026-09-07 03:30 UTC) |
| `LOGBOOK_09062026_192407.md` | Logbook — 5th issue: stale KG fixture, fixed with real evidence; P7 status re-check |
| `LOGBOOK_09062026_184616.md` | Logbook — TODO.md/MASTER.md/LOGBOOK.md created (didn't exist); Step 9 (comparative benchmark) added to the plan |
| `LOGBOOK_09062026_172407.md` | Logbook — Four issues from the last status check, fixed in order |
| `LOGBOOK_09062026_162250.md` | Logbook — Build Kickoff Step 8: on-demand keyword discovery, built and verified live (with a real threshold-calibration correction along the way) |
| `LOGBOOK_09062026_160250.md` | Logbook — Build Kickoff (8-step plan): Steps 1, 3, 4, 6, 7, 2 done with real evidence; Step 5 running; Step 8 next |
| `LOGBOOK_09062026_112233.md` | Logbook — Judgment set grown again (106→126 queries); status check on the recurring auto-tune first |
| `LOGBOOK_09062026_092300.md` | Logbook — KE_AUTO_TUNE first-scheduled-runs check (2026-09-06 09:23 UTC) |
| `LOGBOOK_09042026_112500.md` | Logbook — Recurring auto-tune built, verified live, scheduled; a note on how it got verified |
| `LOGBOOK_09042026_103825.md` | Logbook — auto_tune.py run (2026-09-04 10:38 UTC) |
| `LOGBOOK_09042026_060353.md` | Logbook — Weighted score fusion beats RRF; deployed. Plus: fork points for future exploration |
| `LOGBOOK_09042026_055006.md` | Logbook — Round-2 CV validates rrf_k=1; deployed to production |
| `LOGBOOK_09042026_050500.md` | Logbook — Judgment set grown to 100+ queries per explicit user request; ceiling raised; P2 still fails, unchanged sign |
| `LOGBOOK_09032026_161900.md` | Logbook — GA parameter tuning for P2 confirmed to overfit; not deployed |
| `LOGBOOK_09032026_161500.md` | Logbook — Session paused for unplanned node power-off; GA overfitting test mid-run |
| `LOGBOOK_09032026_155830.md` | Logbook — Grew the judgment set to fix P2; it didn't, and revealed something worse |
| `LOGBOOK_09032026_152832.md` | Logbook — P2 exit criterion FAILS post-merge; root-caused a pre-existing FAISS/registry orphan gap |
| `LOGBOOK_09032026_142903.md` | Logbook — Deploying as a live service, and a real merge-ingest mistake |
| `LOGBOOK_09032026_140900.md` | Logbook — Crawler scheduled, allowlist grown, merge paused mid-run (session stop) |
| `LOGBOOK_09032026_134309.md` | Logbook — Independent live-status re-check, open items restated, docs sync |
| `LOGBOOK_09032026_132923.md` | Logbook — P7: Optional Small-LLM Answer Layer |
| `LOGBOOK_09032026_082933.md` | Logbook — P6: Web Crawl Expansion (allowlisted, not general crawling) |
| `LOGBOOK_09032026_080855.md` | Logbook — P5: Enterprise Connectors & Access Control (ACL core + Git only) |
| `LOGBOOK_09032026_074714.md` | Logbook — P4: Entity Extraction & Knowledge Graph v1 |
| `LOGBOOK_09032026_002053.md` | Logbook — P3: Usage Capture & Learning-to-Rank (infra only, training gated) |
| `LOGBOOK_09032026_000504.md` | Logbook — P2: Hybrid Retrieval (BGE-Small + FAISS/HNSW + RRF) |
| `LOGBOOK_09022026_214005.md` | Logbook — P0/P1 Live Verification (re-run before starting P2) |
| `LOGBOOK_09022026_175124.md` | Logbook — P1: Ingestion & BM25 MVP |
| `LOGBOOK_09022026_173751.md` | Logbook — P0 Kickoff: CPU-First Knowledge Engine Foundations |
