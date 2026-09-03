"""P6 crawl pipeline: robots.txt compliance + per-domain rate limiting +
canonicalization/dedup over an explicit allowlist, saving each fetched page
as an .html file that then passes through the SAME P1 ingestion pipeline
every other corpus document uses -- unchanged, per the exit criterion.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from crawl.allowlist import AllowlistEntry
from crawl.canonicalize import canonicalize_url
from crawl.fetcher import USER_AGENT, fetch_url
from crawl.rate_limiter import PerDomainRateLimiter
from crawl.robots import RobotsChecker


class CrawlState:
    """Tracks canonical URLs already fetched, across runs -- a re-run of the
    same allowlist skips pages it already has, the same incremental spirit
    as ingest.pipeline's content-hash registry."""

    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS crawled (canonical_url TEXT PRIMARY KEY, filename TEXT NOT NULL, fetched_at TEXT NOT NULL)"
        )
        self._conn.commit()

    def already_crawled(self, canonical_url: str) -> bool:
        return self._conn.execute(
            "SELECT 1 FROM crawled WHERE canonical_url = ?", (canonical_url,)
        ).fetchone() is not None

    def record(self, canonical_url: str, filename: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO crawled (canonical_url, filename, fetched_at) VALUES (?, ?, ?)",
            (canonical_url, filename, datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


@dataclass
class CrawlReport:
    fetched: int = 0
    skipped_robots_disallowed: list[str] = field(default_factory=list)
    skipped_duplicate: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0
    politeness_budget_s: float = 0.0

    def within_budget(self) -> bool:
        return self.elapsed_s <= self.politeness_budget_s


def _slug_for(canonical_url: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", canonical_url).strip("_")
    digest = hashlib.sha1(canonical_url.encode("utf-8")).hexdigest()[:8]
    return f"{cleaned[:60]}_{digest}"


def run_crawl(
    allowlist: list[AllowlistEntry],
    output_dir: Path,
    crawl_state_db: Path,
    min_interval_s: float = 3.0,
    politeness_budget_s: float = 60.0,
) -> CrawlReport:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = CrawlReport(politeness_budget_s=politeness_budget_s)
    robots = RobotsChecker()
    rate_limiter = PerDomainRateLimiter(min_interval_s)
    state = CrawlState(crawl_state_db)

    start = time.monotonic()
    for entry in allowlist:
        canonical = canonicalize_url(entry.url)

        if state.already_crawled(canonical):
            report.skipped_duplicate.append(entry.url)
            continue

        if not robots.can_fetch(entry.url, USER_AGENT):
            report.skipped_robots_disallowed.append(entry.url)
            continue

        rate_limiter.wait_if_needed(entry.url)

        try:
            result = fetch_url(entry.url)
        except Exception as exc:  # noqa: BLE001 - report and continue, don't abort the whole crawl
            report.errors.append(f"{entry.url}: {exc}")
            continue

        if result.status_code != 200:
            report.errors.append(f"{entry.url}: HTTP {result.status_code}")
            continue

        filename = f"{_slug_for(canonical)}.html"
        (output_dir / filename).write_text(result.content, encoding="utf-8")
        state.record(canonical, filename)
        report.fetched += 1

    report.elapsed_s = time.monotonic() - start
    state.close()
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from config import get_settings
    from ingest.pipeline import run_ingest

    parser = argparse.ArgumentParser(description="Run the P6 allowlisted crawl, then ingest the fetched pages")
    parser.add_argument("--skip-ingest", action="store_true", help="crawl only, don't run ingest.pipeline afterward")
    args = parser.parse_args(argv)

    from crawl.allowlist import ALLOWLIST

    settings = get_settings()
    report = run_crawl(
        ALLOWLIST, settings.crawl_output_dir, settings.crawl_state_db_path,
        min_interval_s=settings.crawl_min_interval_s, politeness_budget_s=settings.crawl_politeness_budget_s,
    )

    print(f"fetched={report.fetched} skipped_duplicate={len(report.skipped_duplicate)} "
          f"skipped_robots_disallowed={len(report.skipped_robots_disallowed)} errors={len(report.errors)}")
    print(f"elapsed={report.elapsed_s:.1f}s budget={report.politeness_budget_s:.0f}s "
          f"-> {'WITHIN BUDGET' if report.within_budget() else 'OVER BUDGET'}")
    if report.errors:
        print(f"errors: {report.errors}")

    if not args.skip_ingest:
        ingest_report = run_ingest(settings.crawl_output_dir, settings.web_tantivy_index_dir, settings.web_registry_db_path)
        print(f"ingest: scanned={ingest_report.scanned} added={ingest_report.added} "
              f"updated={ingest_report.updated} unchanged={ingest_report.unchanged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
