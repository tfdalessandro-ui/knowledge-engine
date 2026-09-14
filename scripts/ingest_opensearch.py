"""Step 9 helper: ingest data/corpus/ into OpenSearch under the SAME doc_id
scheme judgments.json uses (the file stem), so eval.metrics can score
OpenSearch results against the real judgment set exactly like it scores
this engine's own index -- reuses ingest.parsers.parse_to_text, the same
parser this engine's own P1 pipeline uses, for parity (not a different,
easier-to-index text extraction).
"""
from __future__ import annotations

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ingest.parsers import SUPPORTED_EXTENSIONS, parse_to_text

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = REPO_ROOT / "data" / "corpus"
OPENSEARCH_URL = "http://127.0.0.1:9200"
INDEX = "ke_benchmark_corpus"


def main():
    httpx.delete(f"{OPENSEARCH_URL}/{INDEX}")  # idempotent re-run
    r = httpx.put(f"{OPENSEARCH_URL}/{INDEX}", json={
        "settings": {"index": {"number_of_shards": 1, "number_of_replicas": 0}},
        "mappings": {"properties": {"text": {"type": "text"}, "doc_id": {"type": "keyword"}}},
    }, timeout=15.0)
    print(f"[ingest_opensearch] create index -> {r.status_code}")

    docs, errors = 0, []
    for path in sorted(CORPUS_DIR.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        doc_id = path.stem
        try:
            text = parse_to_text(path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{doc_id}: {exc}")
            continue
        resp = httpx.put(f"{OPENSEARCH_URL}/{INDEX}/_doc/{doc_id}", json={"doc_id": doc_id, "text": text}, timeout=30.0)
        if resp.status_code not in (200, 201):
            errors.append(f"{doc_id}: HTTP {resp.status_code} {resp.text[:200]}")
        docs += 1

    httpx.post(f"{OPENSEARCH_URL}/{INDEX}/_refresh", timeout=15.0)
    count = httpx.get(f"{OPENSEARCH_URL}/{INDEX}/_count", timeout=15.0).json()["count"]
    print(f"[ingest_opensearch] indexed {docs} docs, {len(errors)} errors, "
          f"OpenSearch reports {count} docs in the index")
    if errors:
        print("errors:", errors)


if __name__ == "__main__":
    main()
