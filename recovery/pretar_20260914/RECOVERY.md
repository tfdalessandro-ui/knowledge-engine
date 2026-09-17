# Recovery set: `~/work/knowledge_engine_pretar_backup_20260914`

These are reference copies, not live code. `pytest` doesn't collect them (`testpaths = tests`). They are the only files in the
sensalis-node backup taken just before the 14 Sep 2026 tar-ship → git-clone migration whose content existed nowhere
else: not in `~/work/ose`, and not in any commit of this repo. The comparison was done file by file on 2026-09-17, and each
copy here is byte-identical to the node backup (sha256 verified). `.gitattributes` keeps git from converting their line endings.

The migration kept the files that were in git and silently dropped node-only edits. Some of those edits were **production
features**, still missing from live code as of this commit:

| Lost feature | Backup file(s) here | Current state |
|---|---|---|
| Crawl re-fetch: TTL (`DEFAULT_TTL_DAYS=1.0`) + content-hash change detection, `needs_fetch()`, `content_hash` column migration | `src/crawl/pipeline.py`, `tests/crawl/test_crawl_pipeline.py` (3 TTL tests), `tests/crawl/conftest.py` (mutable-content fixture) | live crawler treats every fetched URL as permanently unchanged (`ose-crawl` logs `unchanged=12`), so the "continuous crawler" isn't actually continuous |
| Crawl allowlist: 7 reviewed entries (Wikipedia: Knowledge graph, Learning to rank, NER, LLM, Vector database; docs.python.org venv; sqlite.org WAL) | `src/crawl/allowlist.py` | live allowlist is 12 URLs |
| Adaptive alpha: `alpha_mode="adaptive"`, per-query alpha via `eval.adaptive_alpha` | `src/eval/hybrid_index.py`, `src/eval/run.py`, `src/api/main.py`, `p7_batch_run.py` | the setting exists but does nothing (TODO item 10); `adaptive_alpha.py` itself was restored 16 Sep |
| On-demand discovery triggered from `/search` when results are sparse (`is_sparse` → `run_discovery`, `discovery_triggered` in the response) | `src/api/main.py`, `tests/api/test_main.py` | `discovery/` package restored 16 Sep but not wired into `/search`, so `discovery_enabled` does nothing |

Superseded (the backup is **older** than the current code; kept only for history): `src/answer/model.py`,
`src/answer/pipeline.py` (pre repetition/fabrication fixes, `repeat_penalty` 1.15), `src/config/__init__.py` (differs only by
the `KE_` prefix), `tests/eval/test_harness.py`, `tests/eval/test_hybrid_vs_bm25.py`, `tests/kg/test_neighbor_retrieval.py`,
and the doc snapshots `HELP.md`, `README.md`, `MASTER.md`, `TODO.md`, `LOGBOOK.md`.

History only: `data/judgments/judgments.json.bak_pre_100q_20260904` and `...bak_pre_grow2_20260906` (judgment set before its
two growth rounds), and `log/*.log` (timer/cron output up to 14 Sep).

Checked redundant and not copied: `data/query_log.db` and `data/merge_review.db` (every backup row is present in the current
databases), `data/auto_tune_state.json` (superseded by a newer run), the corpus documents `doc26`–`doc30` (differ only in
line endings), all 730 other files (byte-identical in `~/work/ose`), and `.venv`, caches and indexes.

Restoring a lost feature means porting it onto current code (which has since changed: instance settings, `OSE_` prefix,
the weighted-fusion rewiring), not copying these files over. Do it one feature at a time, with a regression check each.
