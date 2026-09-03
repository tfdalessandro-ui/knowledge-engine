"""Structural checks on the allowlist itself -- per the roadmap, the list
IS the deliverable, so it should at least be internally well-formed (every
entry reviewed, no duplicates, a stated reason)."""
from crawl.allowlist import ALLOWLIST


def test_allowlist_is_not_empty():
    assert len(ALLOWLIST) > 0


def test_every_entry_has_a_non_empty_reason():
    for entry in ALLOWLIST:
        assert entry.reason.strip() != ""


def test_every_entry_has_a_robots_review_note():
    for entry in ALLOWLIST:
        assert entry.robots_checked.strip() != ""


def test_no_duplicate_urls():
    urls = [e.url for e in ALLOWLIST]
    assert len(urls) == len(set(urls))


def test_entry_domain_matches_its_url():
    from urllib.parse import urlparse

    for entry in ALLOWLIST:
        assert urlparse(entry.url).netloc == entry.domain
