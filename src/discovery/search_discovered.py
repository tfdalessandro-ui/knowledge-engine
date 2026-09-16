"""Queries the SEPARATE discovered-content index and attaches each hit's
provenance record -- this is how a caller (or this module's own CLI, or
the follow-up-search step in a Step 8 demo) confirms a discovered
document is both searchable AND visibly tagged as discovered-via-keyword,
distinct from anything in the main P1/P2 index or P6's web index.
"""
from __future__ import annotations

from dataclasses import dataclass

from discovery.provenance import ProvenanceRecord, ProvenanceStore
from eval.real_index import RealBM25Index


@dataclass
class DiscoveredHit:
    doc_id: str
    provenance: ProvenanceRecord | None


def search_discovered(query: str, settings, k: int = 10) -> list[DiscoveredHit]:
    index = RealBM25Index(settings.discovered_tantivy_index_dir)
    provenance = ProvenanceStore(settings.discovery_provenance_db_path)
    doc_ids = index.search(query, k=k)
    hits = [DiscoveredHit(doc_id=d, provenance=provenance.get(d)) for d in doc_ids]
    provenance.close()
    return hits


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from config import get_settings

    parser = argparse.ArgumentParser(description="Search the Step 8 discovered-content index")
    parser.add_argument("query")
    parser.add_argument("--k", type=int, default=10)
    args = parser.parse_args(argv)

    settings = get_settings()
    hits = search_discovered(args.query, settings, k=args.k)
    if not hits:
        print("no hits in the discovered index")
        return 0
    for h in hits:
        if h.provenance:
            print(f"{h.doc_id}  [discovered-via-keyword: query={h.provenance.source_query!r} "
                  f"source={h.provenance.source_url!r} at={h.provenance.discovered_at}]")
        else:
            print(f"{h.doc_id}  [WARNING: no provenance record found -- should not happen]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
