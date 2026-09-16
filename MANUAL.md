# MANUAL — Using the Knowledge Engine

This is for someone who wants to *use* the engine — ask it questions, check
it's alive, see what it knows. If you want to build or modify it instead,
read `README.md` and `HELP.md` (developer-facing) and `MASTER.md`/`TODO.md`
(current project status) instead.

The engine runs on `sensalis-node`, a machine on the operator's own
network. Everything below assumes you can reach it (either on the LAN, or
via the off-LAN SSH tunnel described in `HELP.md` if you're not on the
LAN).

## Asking it a question

The engine answers over a simple web API, not a chat window. From a
terminal on the same machine (or tunneled in):

```
curl 'http://127.0.0.1:8000/search?q=YOUR+QUESTION+HERE&k=5'
```

- `q` is your question or keywords (URL-encode spaces as `+` or `%20`).
- `k` is how many results you want back (default 10 if you leave it off).

You'll get back JSON: a ranked list of text chunks (`hits`), each with the
source document it came from and a relevance score. There's no
conversational follow-up — every call is a fresh, independent search.

**Example**, and what a real response looks like:
```
curl 'http://127.0.0.1:8000/search?q=okapi+bm25+ranking&k=1'
```
returns something like:
```json
{"query_id":17,"query":"okapi bm25 ranking","hits":[{"doc_id":"...",
"bm25_score":16.2,"vector_score":0.69,"rrf_score":1.0,
"text":"...BM25 is a ranking function used by search engines..."}],
"discovery_triggered":false}
```
If your question comes back with very few or no results, the engine may
automatically go out and search the web for more material on the spot
(`"discovery_triggered":true` when this happens) — see "What it knows"
below for how to see what that found.

## Is it healthy / running right now?

Three checks, from simplest to most detailed:

1. **Quick health ping:**
   ```
   curl http://127.0.0.1:8000/health
   ```
   should return `{"status":"ok"}`. If this doesn't respond at all, the
   engine is down.

2. **Is the service itself running, and for how long:**
   ```
   systemctl --user status ose.service
   ```
   Look for `Active: active (running) since ...` — that timestamp is how
   long it's been continuously up.

3. **Does it actually answer correctly:** run a real query (see above) on
   something you know the answer to and check the result makes sense.
   `/health` only proves the process is alive, not that search results
   are good.

## What it's discovered / crawled

The engine keeps three separate records of what it's found, each for a
different reason:

- **The background crawler** re-checks a fixed, hand-reviewed list of web
  pages once a day (not general web crawling — a short curated list, see
  `src/crawl/allowlist.py` if you want to see exactly which pages). To see
  when each page was last actually re-fetched:
  ```
  sqlite3 data/crawl_state.db "SELECT canonical_url, fetched_at FROM crawled ORDER BY fetched_at DESC;"
  ```

- **On-demand discovery**: when a question you asked came back sparse, the
  engine may have gone and searched the live web for more material right
  then, on your behalf. To see every time this has happened, what was
  searched for, and what it fetched:
  ```
  sqlite3 data/discovery_provenance.db "SELECT query, source_url, discovered_at FROM provenance ORDER BY discovered_at DESC;"
  ```
  Anything found this way is kept in its own separate area, distinct from
  the curated crawler's material — it never silently mixes into the main
  index.

- **The research-to-production loop**: separately from crawling web pages,
  the engine can also identify candidate technique improvements to its own
  ranking (found via a second research-specific crawl, currently limited
  to a handful of arxiv listing pages). Any such candidate sits in a
  holding period (currently 14 days) before it's automatically kept or
  dropped, based on whether it actually improves search quality. To see
  what's pending or decided:
  ```
  sqlite3 data/research_candidates.db "SELECT name, status, decision_date, benchmark_before, benchmark_after FROM candidates;"
  ```

## Changing the engine to a different topic

**Short answer: this needs code changes, not just a setting.** Two parts
of the engine are hardcoded to its current subject matter (search/ranking
technology) and would need to be rewritten by hand for a new topic:

1. **The list of web pages it crawls in the background** — a literal list
   in the code, each page picked and robots.txt-checked by hand for this
   topic.
2. **What it recognizes as an important term/entity** — a hardcoded list of
   words (specific technologies, company names, product names) built by
   scanning this topic's own material. On a new topic, this list would
   need to be rebuilt from scratch or it will recognize nothing.

One part of the engine — the on-demand web-discovery feature described
above — genuinely works on *any* topic already, no changes needed there.

**Before any of that would be worth doing**, a new topic also needs its
own hand-built set of "for this question, this is the right answer"
examples (currently ~126 for the search/ranking topic this engine was
built and tuned on). Without that, there's no way to measure whether the
engine is actually getting better or worse at the new topic — the scores
this manual and the status docs quote are only meaningful for the topic
they were measured on.
