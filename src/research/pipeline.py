"""Thin wrapper reusing crawl.pipeline.run_crawl's exact mechanics
(robots.txt compliance, per-domain rate limiting, dedup) against the
SEPARATE `research_allowlist.RESEARCH_ALLOWLIST` -- never the P6
allowlist. Fetched pages go to `settings.research_crawl_output_dir` /
`settings.research_crawl_state_db_path`, distinct paths from P6's
`crawl_output_dir`/`crawl_state_db_path`, and are NEVER passed through
`ingest.pipeline` into the main or web index -- this is a source feed
for `research/loop.py` to draw candidate techniques from, not searchable
corpus content.
"""
from __future__ import annotations

from crawl.pipeline import CrawlReport, run_crawl
from research.allowlist import RESEARCH_ALLOWLIST

RESEARCH_CRAWL_DELAY_S = 15.0  # arxiv.org's own robots.txt Crawl-delay for User-agent: *


def run_research_crawl(settings) -> CrawlReport:
    return run_crawl(
        RESEARCH_ALLOWLIST,
        settings.research_crawl_output_dir,
        settings.research_crawl_state_db_path,
        min_interval_s=RESEARCH_CRAWL_DELAY_S,
        politeness_budget_s=settings.research_crawl_politeness_budget_s,
    )


def main(argv: list[str] | None = None) -> int:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from config import get_settings

    settings = get_settings()
    report = run_research_crawl(settings)
    print(f"fetched={report.fetched} skipped_duplicate={len(report.skipped_duplicate)} "
          f"skipped_robots_disallowed={len(report.skipped_robots_disallowed)} errors={len(report.errors)}")
    print(f"elapsed={report.elapsed_s:.1f}s budget={report.politeness_budget_s:.0f}s "
          f"-> {'WITHIN BUDGET' if report.within_budget() else 'OVER BUDGET'}")
    if report.errors:
        print(f"errors: {report.errors}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
