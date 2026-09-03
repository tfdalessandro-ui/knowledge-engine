"""Fetches a single URL with a declared, identifiable User-Agent -- good
crawl practice: a site operator inspecting logs should be able to tell what
this bot is and why it's there, not see an anonymous/spoofed browser UA.
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx

USER_AGENT = (
    "CPUFirstKnowledgeEngineBot/0.1 "
    "(+https://github.com/tfdalessandro-ui/knowledge-engine; small research/demo crawl over an explicit allowlist)"
)


@dataclass
class FetchResult:
    url: str
    status_code: int
    content: str


def fetch_url(url: str, timeout_s: float = 10.0) -> FetchResult:
    response = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout_s, follow_redirects=True)
    return FetchResult(url=url, status_code=response.status_code, content=response.text)
