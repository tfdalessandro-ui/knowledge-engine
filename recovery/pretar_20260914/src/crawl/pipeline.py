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


DEFAULT_TTL_DAYS = 1.0  # matches the daily timer's own cadence -- a URL is
# eligible for re-fetch once its last fetch is >= this old. Added 2026-09-06
# after finding crawl.pipeline had NO re-fetch mechanism at all: every URL
# was treated as permanently unchanged once fetched once, so a daily timer
# over this pipeline was not actually continuous (see LOGBOOK_09062026_*.md
# for the full finding). Re-fetching alone isn't enough either -- a content
# hash is compared on every re-fetch so an unchanged page doesn't get
# needlessly re-ingested, only a genuinely changed one does.


class CrawlState:
    """Tracks canonical URLs already fetched, across runs. A URL past its
    TTL is eligible for re-fetch (not skipped forever); `content_hash` is
    compared on every re-fetch so `run_crawl` can tell a genuinely changed
    page from a re-check that found no change."""

    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS crawled (canonical_url TEXT PRIMARY KEY, filename TEXT NOT NULL, "
            "fetched_at TEXT NOT NULL, content_hash TEXT)"
        )
        # migration for a DB created before content_hash existed
        existing_cols = {row[1] for row in self._conn.execute("PRAGMA table_info(crawled)").fetchall()}
        if "content_hash" not in existing_cols:
            self._conn.execute("ALTER TABLE crawled ADD COLUMN content_hash TEXT")
        self._conn.commit()

    def get(self, canonical_url: str) -> tuple[str, str, str | None] | None:
        """Returns (filename, fetched_at, content_hash) or None if never fetched."""
        row = self._conn.execute(
            "SELECT filename, fetched_at, content_hash FROM crawled WHERE canonical_url = ?", (canonical_url,)
        ).fetchone()
        return row

    def needs_fetch(self, canonical_url: str, ttl_days: float) -> bool:
        """True if never fetched, or the last fetch is older than ttl_days --
        NOT the old "already_crawled means skip forever" behavior."""
        row = self.get(canonical_url)
        if row is None:
            return True
        _, fetched_at, _ = row
        age_days = (datetime.now(timezone.utc) - datetime.fromisoformat(fetched_at)).total_seconds() / 86400
        return age_days >= ttl_days

    def record(self, canonical_url: str, filename: str, content_hash: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO crawled (canonical_url, filename, fetched_at, content_hash) VALUES (?, ?, ?, ?)",
            (canonical_url, filename, datetime.now(timezone.utc).isoformat(), content_hash),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


@dataclass
class CrawlReport:
    fetched: int = 0  # brand-new URLs, never seen before
    rechecked_unchanged: list[str] = field(default_factory=list)  # TTL expired, re-fetched, content_hash matched -- no change
    rechecked_changed: list[str] = field(default_factory=list)  # TTL expired, re-fetched, content_hash differs -- real update
    skipped_robots_disallowed: list[str] = field(default_factory=list)
    skipped_duplicate: list[str] = field(default_factory=list)  # still within TTL -- not yet eligible for re-fetch
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
    ttl_days: float = DEFAULT_TTL_DAYS,
) -> CrawlReport:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = CrawlReport(politeness_budget_s=politeness_budget_s)
    robots = RobotsChecker()
    rate_limiter = PerDomainRateLimiter(min_interval_s)
    state = CrawlState(crawl_state_db)

    start = time.monotonic()
    for entry in allowlist:
        canonical = canonicalize_url(entry.url)
        existing = state.get(canonical)

        if not state.needs_fetch(canonical, ttl_days):
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

        new_hash = hashlib.sha256(result.content.encode("utf-8")).hexdigest()
        filename = f"{_slug_for(canonical)}.html"

        if existing is not None:
            _, _, old_hash = existing
            if old_hash == new_hash:
                # TTL had expired, so this WAS actually re-fetched and
                # re-hashed -- just found no real change. Still bump
                # fetched_at so the TTL clock resets from now, not from
                # the original fetch.
                state.record(canonical, filename, new_hash)
                report.rechecked_unchanged.append(entry.url)
                continue
            (output_dir / filename).write_text(result.content, encoding="utf-8")
            state.record(canonical, filename, new_hash)
            report.rechecked_changed.append(entry.url)
            continue

        (output_dir / filename).write_text(result.content, encoding="utf-8")
        state.record(canonical, filename, new_hash)
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

    print(f"fetched={report.fetched} rechecked_unchanged={len(report.rechecked_unchanged)} "
          f"rechecked_changed={len(report.rechecked_changed)} skipped_duplicate={len(report.skipped_duplicate)} "
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
