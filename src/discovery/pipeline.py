"""Step 8: on-demand keyword discovery, triggered when a /search query
returns sparse/no results. Every guardrail from the Build Kickoff plan is
enforced here, in one place, so it's auditable in a single read:

1. robots.txt compliance -- same crawl.robots.RobotsChecker mechanism P6
   uses, checked before every fetch, never bypassed.
2. Domain blocklist -- discovery.blocklist's StevenBlack/hosts-backed
   check, before every fetch.
3. Hard cap -- MAX_URLS_PER_TRIGGER bounds how many URLs a single sparse-
   result trigger can fetch, no matter how many search results come back.
4. Provenance -- every fetched document gets a ProvenanceStore row
   (source_query, source_url, discovered_at) before being ingested.
5. NO LLM ANYWHERE -- the search-API call (discovery.search.web_search),
   candidate filtering (robots + blocklist, both pure rule-based), and
   content extraction (crawl.fetcher.fetch_url, plain HTTP GET, then the
   SAME ingest.pipeline parsing every other document goes through) are
   all traditional/rule-based. Ingestion reuses P1's parser+chunker and
   P2's embedding pipeline exactly (via ingest.pipeline.run_ingest with a
   vector_index_path) -- not reimplemented, not skipped.

Discovered content is kept in its OWN index/registry namespace
(settings.discovered_tantivy_index_dir / discovered_registry_db_path),
separate from both the main P1/P2 index and P6's web_tantivy_index_dir --
never silently merged into either.
"""
from __future__ import annotations

import re
import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from crawl.fetcher import USER_AGENT, fetch_url
from crawl.robots import RobotsChecker
from discovery.blocklist import is_domain_blocked, load_blocklist
from discovery.provenance import ProvenanceStore
from discovery.search import web_search
from ingest.pipeline import run_ingest

MAX_URLS_PER_TRIGGER = 3  # hard cap -- never fetch more than this many URLs for one sparse-result trigger
CANDIDATE_POOL_SIZE = 10  # how many search results to consider before the cap narrows it down


@dataclass
class DiscoveryReport:
    query: str
    candidates_considered: int = 0
    skipped_blocklist: list[str] = field(default_factory=list)
    skipped_robots_disallowed: list[str] = field(default_factory=list)
    fetched: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _slug_for(url: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", url).strip("_")
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    return f"{cleaned[:60]}_{digest}"


def run_discovery(query: str, settings, caller: str = "unknown") -> DiscoveryReport:
    """`caller` identifies what triggered this -- e.g. "api:/search" from
    api/main.py's sparse-result trigger. Defaults to "unknown" so a script
    or REPL call that doesn't pass it is still logged, just visibly
    flagged as not coming through a known path (see provenance.py's
    module docstring for why this exists -- a real untraceable invocation
    happened once, this is the fix)."""
    settings.discovery_output_dir.mkdir(parents=True, exist_ok=True)

    _log_store = ProvenanceStore(settings.discovery_provenance_db_path)
    invocation_id = _log_store.log_invocation(query, caller=caller)
    _log_store.close()
    print(f"[discovery] invocation #{invocation_id} logged (caller={caller!r}, pid={os.getpid()})")

    report = DiscoveryReport(query=query)
    print(f"[discovery] sparse results for {query!r} -- triggering on-demand web discovery")

    candidates = web_search(query, limit=CANDIDATE_POOL_SIZE)
    report.candidates_considered = len(candidates)
    print(f"[discovery] search API returned {len(candidates)} candidates (pool capped at {CANDIDATE_POOL_SIZE})")

    blocklist = load_blocklist(settings.discovery_blocklist_cache_path)
    print(f"[discovery] domain blocklist loaded: {len(blocklist)} domains (source: StevenBlack/hosts)")

    robots = RobotsChecker()
    provenance = ProvenanceStore(settings.discovery_provenance_db_path)

    for i, candidate in enumerate(candidates):
        if len(report.fetched) >= MAX_URLS_PER_TRIGGER:
            print(f"[discovery] hard cap of {MAX_URLS_PER_TRIGGER} URLs reached -- stopping, "
                  f"{len(candidates) - i} candidates left unconsidered by design")
            break

        domain = urlparse(candidate.url).netloc

        print(f"[discovery] checking blocklist for domain: {domain}")
        if is_domain_blocked(domain, blocklist):
            print(f"[discovery]   BLOCKED (in StevenBlack/hosts) -- skipping {candidate.url}")
            report.skipped_blocklist.append(candidate.url)
            continue

        print(f"[discovery] checking robots.txt for: {candidate.url}")
        if not robots.can_fetch(candidate.url, USER_AGENT):
            print(f"[discovery]   DISALLOWED by robots.txt -- skipping {candidate.url}")
            report.skipped_robots_disallowed.append(candidate.url)
            continue

        try:
            print(f"[discovery] fetching: {candidate.url}")
            result = fetch_url(candidate.url)
        except Exception as exc:  # noqa: BLE001 - report and continue, don't abort the whole trigger
            report.errors.append(f"{candidate.url}: {exc}")
            continue

        if result.status_code != 200:
            report.errors.append(f"{candidate.url}: HTTP {result.status_code}")
            continue

        doc_id = _slug_for(candidate.url)
        filename = f"{doc_id}.html"
        (settings.discovery_output_dir / filename).write_text(result.content, encoding="utf-8")
        provenance.record(doc_id=doc_id, source_query=query, source_url=candidate.url)
        report.fetched.append(candidate.url)
        print(f"[discovery]   fetched OK, tagged provenance (query={query!r}, source={candidate.url!r})")

    provenance.close()

    if report.fetched:
        print(f"[discovery] ingesting {len(report.fetched)} newly fetched document(s) into the "
              f"SEPARATE discovered index (same P1/P2 pipeline, distinct namespace)...")
        ingest_report = run_ingest(
            settings.discovery_output_dir,
            settings.discovered_tantivy_index_dir,
            settings.discovered_registry_db_path,
            vector_index_path=settings.discovered_faiss_index_path,
            vector_registry_db=settings.discovered_vector_registry_db_path,
        )
        print(f"[discovery] ingest: scanned={ingest_report.scanned} added={ingest_report.added} "
              f"updated={ingest_report.updated} unchanged={ingest_report.unchanged}")

    return report


MIN_MEANINGFUL_BM25_SCORE = 5.0  # calibrated live 2026-09-06 against two real
# data points, not guessed: an off-topic query ("zebra migration patterns
# east africa" against this search-infra corpus) returned bm25_score=4.29
# from a single incidental token overlap (an FTS5-doc page happened to
# share one query word) -- "not None" alone was too weak a bar, and even
# a naive round-number threshold like 3.0 would NOT have excluded this
# real case. Genuinely on-topic queries this session scored 5.6-15+.
# 5.0 sits strictly between the one confirmed false-positive (4.29) and
# the confirmed real matches -- a two-point calibration, not a
# statistically robust one; worth revisiting with more real query/score
# pairs if this heuristic misfires again.


def is_sparse(hits, threshold: int) -> bool:
    """`hits` is the list of DetailedHit from HybridIndex.search_detailed().
    Raw hit COUNT is a bad sparsity signal for this hybrid engine: the
    vector side always pads results with SOMETHING (weak cosine
    similarity never truly hits zero), so a k=10 request nearly always
    returns 10 hits regardless of whether any of them are genuinely
    relevant -- confirmed live, not assumed (see LOGBOOK_09062026_*.md,
    Step 8). A plain "bm25_score is not None" check ALSO turned out too
    weak, confirmed live the same way: a single incidental token overlap
    can still produce a small nonzero score for an unrelated query. The
    real signal used here: none of the top `threshold` hits clears
    MIN_MEANINGFUL_BM25_SCORE."""
    top = hits[:threshold]
    real_bm25_matches = sum(1 for h in top if h.bm25_score is not None and h.bm25_score >= MIN_MEANINGFUL_BM25_SCORE)
    return real_bm25_matches == 0
