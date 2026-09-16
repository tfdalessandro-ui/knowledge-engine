"""The RESEARCH crawl allowlist -- deliberately a SEPARATE list from
`crawl/allowlist.py`'s P6 allowlist, not an extension of it. P6's
allowlist targets on-topic reference pages that get merged into the main
searchable corpus (`data/corpus/`). This allowlist targets IR/KG/LTR/
genetic-algorithm/swarm-intelligence RESEARCH SOURCES for the
research-to-production loop (`research/loop.py`) to draw candidate
techniques from -- fetched pages here go to `data/research_papers/`
and a separate `data/research_crawl_state.db`, and are NEVER merged into
the main corpus or its index. Same discipline as P6: every entry's
robots.txt was checked directly (not assumed) before being added here.

arXiv's own robots.txt (checked 2026-09-06) sets `Crawl-delay: 15` for
the generic `User-agent: *` class this project's declared bot falls
under -- `research/pipeline.py` uses that value, not P6's crawl's
default 3.0s, for exactly this reason. `/list` and `/abs` are both
explicitly `Allow`ed for `User-agent: *`; `/search`, `/api`, and several
others are `Disallow`ed -- this allowlist only uses `/list` category
pages, never a disallowed path.
"""
from __future__ import annotations

from crawl.allowlist import AllowlistEntry

RESEARCH_ALLOWLIST: list[AllowlistEntry] = [
    AllowlistEntry(
        url="https://arxiv.org/list/cs.IR/recent",
        domain="arxiv.org",
        reason="Information Retrieval category listing -- IR/BM25/LTR/hybrid-search research, directly on-topic for this project's own P1-P3.",
        robots_checked="2026-09-06: /list is in arxiv.org's Allow list for User-agent: *; Crawl-delay: 15 respected by research/pipeline.py.",
    ),
    AllowlistEntry(
        url="https://arxiv.org/list/cs.NE/recent",
        domain="arxiv.org",
        reason="Neural and Evolutionary Computing category listing -- the standard arXiv category for genetic-algorithm/swarm-intelligence research, on-topic for this project's own GA-tuning work (Step 7).",
        robots_checked="2026-09-06: same arxiv.org check as above.",
    ),
    AllowlistEntry(
        url="https://arxiv.org/list/cs.AI/recent",
        domain="arxiv.org",
        reason="General AI category listing -- broader knowledge-graph/reranking technique coverage than cs.IR/cs.NE alone cover individually.",
        robots_checked="2026-09-06: same arxiv.org check as above.",
    ),
]
