"""Integration test for run_crawl, entirely against the local test server
(tests/crawl/conftest.py) -- proves the mechanism (robots compliance, rate
limiting, canonicalization/dedup, politeness-budget accounting) without
depending on any real external site's availability."""
from crawl.allowlist import AllowlistEntry
from crawl.pipeline import run_crawl


def test_fetches_allowed_pages_and_writes_html(tmp_path, local_server):
    allowlist = [AllowlistEntry(f"{local_server}/page1", "127.0.0.1", "test", "n/a")]
    report = run_crawl(allowlist, tmp_path / "out", tmp_path / "state.db", min_interval_s=0.01)

    assert report.fetched == 1
    assert not report.errors
    html_files = list((tmp_path / "out").glob("*.html"))
    assert len(html_files) == 1
    assert "Hello from the test server" in html_files[0].read_text(encoding="utf-8")


def test_disallowed_page_is_skipped_not_fetched(tmp_path, local_server):
    allowlist = [AllowlistEntry(f"{local_server}/disallowed", "127.0.0.1", "test", "n/a")]
    report = run_crawl(allowlist, tmp_path / "out", tmp_path / "state.db", min_interval_s=0.01)

    assert report.fetched == 0
    assert report.skipped_robots_disallowed == [f"{local_server}/disallowed"]
    assert list((tmp_path / "out").glob("*.html")) == []


def test_rerun_skips_already_crawled_urls(tmp_path, local_server):
    allowlist = [AllowlistEntry(f"{local_server}/page1", "127.0.0.1", "test", "n/a")]
    run_crawl(allowlist, tmp_path / "out", tmp_path / "state.db", min_interval_s=0.01)
    second_report = run_crawl(allowlist, tmp_path / "out", tmp_path / "state.db", min_interval_s=0.01)

    assert second_report.fetched == 0
    assert second_report.skipped_duplicate == [f"{local_server}/page1"]


def test_politeness_budget_pass(tmp_path, local_server):
    allowlist = [AllowlistEntry(f"{local_server}/page1", "127.0.0.1", "test", "n/a")]
    report = run_crawl(allowlist, tmp_path / "out", tmp_path / "state.db", min_interval_s=0.01, politeness_budget_s=30.0)
    assert report.within_budget() is True


def test_politeness_budget_fail_when_set_impossibly_low(tmp_path, local_server):
    allowlist = [AllowlistEntry(f"{local_server}/page1", "127.0.0.1", "test", "n/a")]
    report = run_crawl(allowlist, tmp_path / "out", tmp_path / "state.db", min_interval_s=0.01, politeness_budget_s=0.0)
    assert report.within_budget() is False


def test_multiple_distinct_pages_all_fetched(tmp_path, local_server):
    allowlist = [
        AllowlistEntry(f"{local_server}/page1", "127.0.0.1", "test", "n/a"),
        AllowlistEntry(f"{local_server}/page2", "127.0.0.1", "test", "n/a"),
    ]
    report = run_crawl(allowlist, tmp_path / "out", tmp_path / "state.db", min_interval_s=0.01)
    assert report.fetched == 2
