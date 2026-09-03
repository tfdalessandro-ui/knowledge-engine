"""Per-domain politeness rate limiting: never fetch two pages from the same
domain faster than `min_interval_s` apart, regardless of how many domains
are being crawled in the same run.
"""
from __future__ import annotations

import time
from urllib.parse import urlparse


class PerDomainRateLimiter:
    def __init__(self, min_interval_s: float):
        self._min_interval_s = min_interval_s
        self._last_fetch_at: dict[str, float] = {}

    def wait_if_needed(self, url: str) -> float:
        """Sleeps if needed, returns how long it slept (seconds)."""
        domain = urlparse(url).netloc
        now = time.monotonic()
        last = self._last_fetch_at.get(domain)
        slept = 0.0
        if last is not None:
            elapsed = now - last
            remaining = self._min_interval_s - elapsed
            if remaining > 0:
                time.sleep(remaining)
                slept = remaining
        self._last_fetch_at[domain] = time.monotonic()
        return slept
