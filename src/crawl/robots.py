"""robots.txt compliance, via the stdlib (`urllib.robotparser`) -- no new
dependency needed for the parsing logic. Caches one parser per domain so a
multi-page crawl of the same domain only fetches robots.txt once.

Deliberately does NOT use `RobotFileParser.read()` to fetch robots.txt:
verified directly that it fetches with urllib's bare default User-Agent
("Python-urllib/x.y"), and Wikipedia (among other sites) returns HTTP 403
for that UA specifically. `read()` swallows that error internally and sets
`disallow_all=True` as a conservative fallback -- meaning every URL on that
domain silently reads as "disallowed", not because robots.txt actually
disallows it, but because the crawler couldn't even read the rules under an
anonymous/unidentified UA. Fetching robots.txt ourselves with the same
declared User-Agent the real crawl uses (see fetcher.py) avoids this.
"""
from __future__ import annotations

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from crawl.fetcher import USER_AGENT


class RobotsChecker:
    def __init__(self):
        self._parsers: dict[str, RobotFileParser] = {}

    def _get_parser(self, url: str) -> RobotFileParser:
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain not in self._parsers:
            robots_url = f"{parsed.scheme}://{domain}/robots.txt"
            parser = RobotFileParser()
            parser.set_url(robots_url)
            try:
                response = httpx.get(robots_url, headers={"User-Agent": USER_AGENT}, timeout=10.0)
                if response.status_code == 200:
                    parser.parse(response.text.splitlines())
                elif response.status_code >= 500:
                    # RFC 9309: a server error means the policy can't be determined --
                    # be cautious, not permissive, until it's actually readable.
                    parser.disallow_all = True
                else:
                    # 4xx (including 404, the common "no robots.txt" case): treat as
                    # unrestricted, per RFC 9309's guidance for an unreachable/absent file.
                    parser.allow_all = True
            except Exception:  # noqa: BLE001 - network error fetching robots.txt itself: be cautious
                parser.disallow_all = True
            self._parsers[domain] = parser
        return self._parsers[domain]

    def can_fetch(self, url: str, user_agent: str) -> bool:
        return self._get_parser(url).can_fetch(user_agent, url)
