"""Entity extraction + knowledge graph pipeline: scans data/corpus/,
extracts entities and relations per document, resolves entities (exact
auto-resolve, fuzzy candidates queued for manual review), and writes
everything to Memgraph.

Unlike ingest.pipeline (P1/P2), this always does a full pass over the
corpus rather than diffing by content hash -- P4's scope is small enough
(a few dozen documents) that re-extraction is cheap, and entity resolution
depends on having seen the whole corpus's entity set, not just one file in
isolation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ingest.parsers import SUPPORTED_EXTENSIONS, parse_to_text
from kg.graph_store import MemgraphStore
from kg.ner import extract_entities
from kg.relations import extract_relations
from kg.resolution import EntityResolver, MergeReviewQueue


@dataclass
class KGReport:
    documents_processed: int = 0
    entities_extracted: int = 0
    relations_extracted: int = 0
    merge_candidates_queued: int = 0
    errors: list[str] = field(default_factory=list)


def run_kg_extraction(corpus_dir: Path, memgraph_uri: str, merge_review_db: Path) -> KGReport:
    report = KGReport()
    review_queue = MergeReviewQueue(merge_review_db)
    resolver = EntityResolver(review_queue)

    with MemgraphStore(memgraph_uri) as store:
        for path in sorted(corpus_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue

            doc_id = path.stem
            try:
                text = parse_to_text(path)
            except Exception as exc:  # noqa: BLE001 - report and continue
                report.errors.append(f"{doc_id}: {exc}")
                continue

            entities = extract_entities(text)
            relations = extract_relations(text, entities)
            report.documents_processed += 1

            cid_by_text: dict[str, str] = {}
            for entity in entities:
                cid = resolver.resolve(entity.text, entity.label)
                cid_by_text[entity.text] = cid
                store.upsert_entity(cid, entity.text, entity.label, doc_id)
                report.entities_extracted += 1

            for relation in relations:
                subj_cid = cid_by_text.get(relation.subject)
                obj_cid = cid_by_text.get(relation.object)
                if subj_cid and obj_cid:
                    store.upsert_relation(subj_cid, relation.relation, obj_cid)
                    report.relations_extracted += 1

    report.merge_candidates_queued = len(review_queue.list_pending())
    review_queue.close()
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from config import get_settings

    parser = argparse.ArgumentParser(description="Run entity extraction + knowledge graph construction")
    parser.add_argument("--corpus", type=Path, default=None)
    args = parser.parse_args(argv)

    settings = get_settings()
    report = run_kg_extraction(args.corpus or settings.corpus_dir, settings.memgraph_uri, settings.merge_review_db_path)

    print(f"documents_processed={report.documents_processed} entities_extracted={report.entities_extracted} "
          f"relations_extracted={report.relations_extracted} merge_candidates_queued={report.merge_candidates_queued}")
    if report.errors:
        print(f"errors: {report.errors}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
