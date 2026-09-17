"""The P6 allowlist -- per the roadmap's own framing, this list IS the
deliverable, not a formality: "treat the list as the deliverable" because
scope drift here is a legal/ToS exposure risk, not a shortcut.

The original roadmap's example language ("OEM sites and trade
publications") is a generic template illustration, not literal to this
project -- this repo has no auto-parts/enterprise business context, so
picking real OEM sites to name here would be inventing a fictitious
justification. Instead: a small set of pages genuinely on-topic for this
project's own subject matter (search/ranking/retrieval), each checked
directly against its domain's actual robots.txt before being added here
(not assumed permissive) -- see the P6 logbook for what was checked and,
for one candidate (fastapi.tiangolo.com, an ambiguous "content signals"
robots.txt with no explicit permission), why it was deliberately NOT added
rather than treated as a gray-area yes.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AllowlistEntry:
    url: str
    domain: str
    reason: str
    robots_checked: str  # date-of-review marker, human-readable -- not machine-parsed


ALLOWLIST: list[AllowlistEntry] = [
    AllowlistEntry(
        url="https://en.wikipedia.org/wiki/Okapi_BM25",
        domain="en.wikipedia.org",
        reason="Background reference for this project's own BM25 ranking implementation (P1).",
        robots_checked="2026-09-03: /wiki/<Article> not in Wikipedia's Disallow list (only /wiki/Special: variants are)",
    ),
    AllowlistEntry(
        url="https://en.wikipedia.org/wiki/Tf%E2%80%93idf",
        domain="en.wikipedia.org",
        reason="Background reference for TF-IDF, BM25's predecessor, discussed in this project's own corpus.",
        robots_checked="2026-09-03: same Wikipedia robots.txt check as above",
    ),
    AllowlistEntry(
        url="https://en.wikipedia.org/wiki/Hierarchical_navigable_small_world",
        domain="en.wikipedia.org",
        reason="Background reference for HNSW, the vector-index structure this project's P2 uses (FAISS).",
        robots_checked="2026-09-03: same Wikipedia robots.txt check as above",
    ),
    AllowlistEntry(
        url="https://www.sqlite.org/fts5.html",
        domain="www.sqlite.org",
        reason="Official documentation for SQLite FTS5, referenced in this project's own P1 corpus.",
        robots_checked="2026-09-03: /fts5.html not in sqlite.org's Disallow list (/cvstrac, /src, /docsrc, /cgi, /contrib)",
    ),
    AllowlistEntry(
        url="https://docs.python.org/3/library/sqlite3.html",
        domain="docs.python.org",
        reason="Official Python stdlib sqlite3 documentation, the module this project's own SQLite stores use.",
        robots_checked="2026-09-03: /3/library/ not in docs.python.org's Disallow list (EOL 2.x/3.0-3.9 versions and /dev, /release are)",
    ),
    AllowlistEntry(
        url="https://en.wikipedia.org/wiki/Knowledge_graph",
        domain="en.wikipedia.org",
        reason="Background reference for the knowledge graph this project's own P4 builds.",
        robots_checked="2026-09-03: same Wikipedia robots.txt check as the other en.wikipedia.org entries (/wiki/<Article> allowed)",
    ),
    AllowlistEntry(
        url="https://en.wikipedia.org/wiki/Learning_to_rank",
        domain="en.wikipedia.org",
        reason="Background reference for learning-to-rank, the technique this project's own P3 (LightGBM reranker) implements.",
        robots_checked="2026-09-03: same Wikipedia robots.txt check as the other en.wikipedia.org entries",
    ),
    AllowlistEntry(
        url="https://en.wikipedia.org/wiki/Named-entity_recognition",
        domain="en.wikipedia.org",
        reason="Background reference for NER, the technique this project's own P4 (spaCy + EntityRuler) implements.",
        robots_checked="2026-09-03: same Wikipedia robots.txt check as the other en.wikipedia.org entries",
    ),
    AllowlistEntry(
        url="https://en.wikipedia.org/wiki/Large_language_model",
        domain="en.wikipedia.org",
        reason="Background reference for the small-LLM answer layer this project's own P7 implements (Qwen2.5-3B via llama.cpp).",
        robots_checked="2026-09-03: same Wikipedia robots.txt check as the other en.wikipedia.org entries",
    ),
    AllowlistEntry(
        url="https://en.wikipedia.org/wiki/Vector_database",
        domain="en.wikipedia.org",
        reason="Background reference for the vector index (FAISS/HNSW) this project's own P2 builds.",
        robots_checked="2026-09-03: same Wikipedia robots.txt check as the other en.wikipedia.org entries",
    ),
    AllowlistEntry(
        url="https://docs.python.org/3/library/venv.html",
        domain="docs.python.org",
        reason="Official Python stdlib venv documentation, the tool this project's own setup (README Quick start) uses directly.",
        robots_checked="2026-09-03: same docs.python.org /3/library/ check as the sqlite3.html entry above",
    ),
    AllowlistEntry(
        url="https://www.sqlite.org/wal.html",
        domain="www.sqlite.org",
        reason="Official SQLite WAL-mode documentation -- background reading on a concurrency mode directly relevant to this project's own SQLite stores being accessed from multiple threads (see the QueryLog/DocumentRegistry thread-safety note in HELP.md).",
        robots_checked="2026-09-03: /wal.html not in sqlite.org's Disallow list, same check as the fts5.html entry above",
    ),
]
