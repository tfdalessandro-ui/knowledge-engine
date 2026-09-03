"""URL canonicalization for crawl dedup: two URLs that reach the same page
(different query-param order, tracking params, trailing slash, fragment)
should map to the same canonical form so the crawler never fetches or
indexes the same content twice under different-looking URLs.
"""
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_TRACKING_PARAM_PREFIXES = ("utm_", "fbclid", "gclid", "ref", "source")


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = "https"  # normalize http -> https for dedup purposes
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[len("www."):]
    path = parsed.path.rstrip("/") or "/"

    kept_params = [
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if not any(k.lower().startswith(p) for p in _TRACKING_PARAM_PREFIXES)
    ]
    kept_params.sort()
    query = urlencode(kept_params)

    return urlunparse((scheme, netloc, path, "", query, ""))
