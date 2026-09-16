"""Web-search client for Step 8 -- the self-hosted SearXNG instance
already running on this node (127.0.0.1:8888, confirmed live 2026-09-06;
see sensalis-node-ops-model, an unrelated project's memory, for why it's
there -- reused here, not re-deployed). Rule-based only: sends the query
text verbatim, no LLM query expansion or rewriting, and returns raw
results for the caller to filter mechanically (robots.txt + blocklist).
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx

SEARXNG_URL = "http://127.0.0.1:8888/search"


@dataclass
class WebSearchResult:
    url: str
    title: str


def web_search(query: str, base_url: str = SEARXNG_URL, limit: int = 10, timeout_s: float = 15.0) -> list[WebSearchResult]:
    response = httpx.get(base_url, params={"q": query, "format": "json"}, timeout=timeout_s)
    response.raise_for_status()
    data = response.json()
    results = []
    for r in data.get("results", [])[:limit]:
        url = r.get("url")
        if url:
            results.append(WebSearchResult(url=url, title=r.get("title", "")))
    return results
