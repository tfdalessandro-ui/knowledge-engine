"""Domain blocklist for Step 8 on-demand discovery. Named concrete
source, per the plan's requirement: StevenBlack/hosts
(https://github.com/StevenBlack/hosts, raw file at
https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts) -- a
unified hosts file merging malware/ad/tracking domains from reputable
sources, actively maintained, ~80,000 domains as of 2026-09-06 (verified
live: `curl` returned 200, `Number of unique domains: 79,994` in the
file's own header). Chosen over inventing a project-local list because
Step 8 explicitly asks for open-web discovery (not a small reviewed
allowlist like P6), so a broad, independently-maintained safety net
matters more here than it does for P6's curated few URLs.

Cached locally (re-fetched if the cache is older than BLOCKLIST_TTL_DAYS)
so every discovery trigger doesn't re-download an ~80k-line file.
"""
from __future__ import annotations

import time
from pathlib import Path

import httpx

BLOCKLIST_URL = "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts"
BLOCKLIST_TTL_DAYS = 7


def _parse_hosts_format(text: str) -> set[str]:
    domains = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ("0.0.0.0", "127.0.0.1"):
            domain = parts[1].strip().lower()
            if domain not in ("localhost", "localhost.localdomain", "local", "broadcasthost"):
                domains.add(domain)
    return domains


def load_blocklist(cache_path: Path) -> set[str]:
    """Returns the cached blocklist, re-fetching if missing or stale.
    On any fetch failure with no usable cache, returns an empty set and
    lets the caller decide how to handle "blocklist unavailable" --
    silently treating everything as blocked would be its own kind of
    unannounced behavior change."""
    if cache_path.exists():
        age_days = (time.time() - cache_path.stat().st_mtime) / 86400
        if age_days < BLOCKLIST_TTL_DAYS:
            return _parse_hosts_format(cache_path.read_text())

    try:
        response = httpx.get(BLOCKLIST_URL, timeout=30.0)
        if response.status_code == 200:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(response.text)
            return _parse_hosts_format(response.text)
    except Exception:  # noqa: BLE001 - network error fetching the blocklist itself
        pass

    if cache_path.exists():
        return _parse_hosts_format(cache_path.read_text())
    return set()


def is_domain_blocked(domain: str, blocklist: set[str]) -> bool:
    return domain.lower() in blocklist
