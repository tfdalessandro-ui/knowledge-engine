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


def test_rerun_within_ttl_still_skips(tmp_path, local_server):
    """The original skip-forever bug this fixes: confirms a re-run still
    correctly skips when the TTL genuinely hasn't expired (ttl_days=1.0,
    default, and no real time passes in a test)."""
    allowlist = [AllowlistEntry(f"{local_server}/page1", "127.0.0.1", "test", "n/a")]
    run_crawl(allowlist, tmp_path / "out", tmp_path / "state.db", min_interval_s=0.01, ttl_days=1.0)
    second_report = run_crawl(allowlist, tmp_path / "out", tmp_path / "state.db", min_interval_s=0.01, ttl_days=1.0)
    assert second_report.fetched == 0
    assert second_report.rechecked_unchanged == []
    assert second_report.rechecked_changed == []
    assert second_report.skipped_duplicate == [f"{local_server}/page1"]


def test_rerun_past_ttl_rechecks_and_finds_unchanged(tmp_path, local_server):
    """The actual fix: once the TTL has expired (ttl_days=0.0 forces
    every re-run to be eligible), the URL gets genuinely re-fetched and
    re-hashed -- and since the test server serves the same content both
    times, it's correctly classified as "rechecked, no change" rather
    than either "skipped forever" (the old bug) or "fetched as new"
    (which would double-count it)."""
    allowlist = [AllowlistEntry(f"{local_server}/page1", "127.0.0.1", "test", "n/a")]
    first = run_crawl(allowlist, tmp_path / "out", tmp_path / "state.db", min_interval_s=0.01, ttl_days=0.0)
    assert first.fetched == 1

    second = run_crawl(allowlist, tmp_path / "out", tmp_path / "state.db", min_interval_s=0.01, ttl_days=0.0)
    assert second.fetched == 0
    assert second.rechecked_unchanged == [f"{local_server}/page1"]
    assert second.rechecked_changed == []
    assert second.skipped_duplicate == []


def test_content_hash_change_is_detected_as_rechecked_changed(tmp_path, local_server_with_mutable_content):
    """A real content change on re-fetch (past TTL) is classified as
    "rechecked, changed" -- distinct from both a fresh fetch and an
    unchanged recheck, and the on-disk file is actually overwritten with
    the new content."""
    server, set_content = local_server_with_mutable_content
    allowlist = [AllowlistEntry(f"{server}/mutable", "127.0.0.1", "test", "n/a")]

    set_content("version one")
    first = run_crawl(allowlist, tmp_path / "out", tmp_path / "state.db", min_interval_s=0.01, ttl_days=0.0)
    assert first.fetched == 1
    html_file = next((tmp_path / "out").glob("*.html"))
    assert "version one" in html_file.read_text(encoding="utf-8")

    set_content("version two -- genuinely different content")
    second = run_crawl(allowlist, tmp_path / "out", tmp_path / "state.db", min_interval_s=0.01, ttl_days=0.0)
    assert second.rechecked_changed == [f"{server}/mutable"]
    assert second.rechecked_unchanged == []
    assert "version two" in html_file.read_text(encoding="utf-8")
