"""Step 9 (Build Kickoff plan): comparative benchmark -- this engine vs.
SearXNG, OpenSearch (self-hosted Elasticsearch-API-compatible), and
Google/Bing API, on two independent dimensions:

  A. Relevance quality (nDCG@10 / MRR / recall@20), reusing the exact
     metric functions from eval.metrics -- same computation as every
     other phase's baseline number.
  B. Speed & resource efficiency (p50/p95 client-side latency; server-side
     CPU/RSS sampled via `docker stats` for the two containerized targets
     and /proc for this engine's own uvicorn process).

Methodology note, stated up front rather than buried in a comment: this
project's own judgment set (data/judgments/judgments.json) was built
against a corpus that is MOSTLY private/hand-authored (project-internal
facts like "Hetzner offers CCX23", "P2 uses hybrid fusion") plus a SMALL
subset of real, public web pages (Wikipedia/sqlite.org/docs.python.org,
the ones data/crawl_state.db actually fetched). A general web search
engine (SearXNG, Google, Bing) cannot possibly return the private-fact
documents -- they aren't on the web. Scoring SearXNG against the FULL
judgment set would therefore be a meaningless, unfairly-low number, not
a real capability comparison. So:
  - This engine and OpenSearch (both index the SAME corpus) are scored
    against the FULL judgment set.
  - SearXNG (and Google/Bing, if credentials existed) are scored against
    the SUBSET of queries whose judged-relevant document is one of the
    real public URLs -- the only queries a web search engine could
    possibly get right. That subset is computed here, not assumed.
Both numbers are reported, clearly labeled, never conflated.
"""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import get_settings
from eval.metrics import mean, ndcg_at_k, reciprocal_rank, recall_at_k

REPO_ROOT = Path(__file__).resolve().parent.parent
JUDGMENTS_PATH = REPO_ROOT / "data" / "judgments" / "judgments.json"
CORPUS_DIR = REPO_ROOT / "data" / "corpus"

ENGINE_URL = "http://127.0.0.1:8000/search"
SEARXNG_URL = "http://127.0.0.1:8888/search"
OPENSEARCH_URL = "http://127.0.0.1:9200"
OPENSEARCH_INDEX = "ke_benchmark_corpus"


def load_judgments() -> dict[str, dict[str, int]]:
    rows = json.loads(JUDGMENTS_PATH.read_text(encoding="utf-8"))
    by_query: dict[str, dict[str, int]] = {}
    for r in rows:
        by_query.setdefault(r["query"], {})[r["doc_id"]] = r["relevance"]
    return by_query


# Map a crawled doc_id (e.g. "https_en_wikipedia_org_wiki_Okapi_BM25_da69a5a0")
# back to a real URL substring we can match against a SearXNG result URL.
# The doc_id encoding is deterministic: scheme_host_path..._<8charhash>.
def url_relevant_docs(judgments_by_query: dict[str, dict[str, int]]) -> dict[str, str]:
    """doc_id -> a distinctive URL substring, for the small set of judgment
    doc_ids that are real crawled web pages (doc_id starts with 'https_')."""
    out = {}
    for docs in judgments_by_query.values():
        for doc_id in docs:
            if doc_id.startswith("https_") or doc_id.startswith("http_"):
                # strip the trailing _<8hex> hash suffix kept in the corpus filename
                stem = doc_id.rsplit("_", 1)[0] if len(doc_id.rsplit("_", 1)[-1]) == 8 else doc_id
                out[doc_id] = stem
    return out


def web_subset(judgments_by_query: dict[str, dict[str, int]]) -> dict[str, dict[str, int]]:
    url_docs = {d for docs in judgments_by_query.values() for d, rel in docs.items() if (d.startswith("https_") or d.startswith("http_")) and rel > 0}
    return {q: docs for q, docs in judgments_by_query.items() if any(d in url_docs for d in docs)}


class EngineIndex:
    name = "this-engine"

    def search(self, query: str, k: int) -> list[str]:
        r = httpx.get(ENGINE_URL, params={"q": query, "k": k}, timeout=30.0)
        r.raise_for_status()
        hits = r.json().get("hits", [])
        # chunk_id like "doc01_bm25::0" -> doc_id "doc01_bm25"; dedupe, keep first-seen order
        seen, out = set(), []
        for h in hits:
            doc_id = h["doc_id"]
            if doc_id not in seen:
                seen.add(doc_id)
                out.append(doc_id)
        return out


class OpenSearchIndex:
    name = "opensearch"

    def search(self, query: str, k: int) -> list[str]:
        r = httpx.post(
            f"{OPENSEARCH_URL}/{OPENSEARCH_INDEX}/_search",
            json={"query": {"match": {"text": query}}, "size": k},
            timeout=30.0,
        )
        r.raise_for_status()
        return [h["_id"] for h in r.json()["hits"]["hits"]]


class SearXNGIndex:
    """Only meaningful on the web_subset judgment queries -- see module
    docstring. Maps a SearXNG result URL back to a judgment doc_id by
    substring match against the deterministic doc_id->URL encoding."""

    name = "searxng"

    def __init__(self, doc_id_to_url_stem: dict[str, str]):
        self._map = doc_id_to_url_stem

    def _url_to_doc_id(self, url: str) -> str | None:
        host_path = (urlparse(url).netloc + urlparse(url).path).replace(".", "_").replace("/", "_").replace("-", "_")
        for doc_id, stem in self._map.items():
            # stem is doc_id minus its trailing hash; compare on the readable core
            core = stem.replace("https_", "").replace("http_", "")
            if core[:40] in host_path.replace("https_", "").replace("http_", ""):
                return doc_id
        return None

    def search(self, query: str, k: int) -> list[str]:
        r = httpx.get(SEARXNG_URL, params={"q": query, "format": "json"}, timeout=15.0)
        r.raise_for_status()
        results = r.json().get("results", [])[:k]
        out = []
        for res in results:
            doc_id = self._url_to_doc_id(res.get("url", ""))
            if doc_id:
                out.append(doc_id)
        return out


def run_relevance(index, judgments_by_query: dict[str, dict[str, int]], k_ndcg=10, k_recall=20):
    ndcgs, rrs, recalls = [], [], []
    errors = 0
    for query, judgments in judgments_by_query.items():
        try:
            ranked = index.search(query, max(k_ndcg, k_recall))
        except Exception as exc:  # noqa: BLE001
            print(f"  [{index.name}] query failed: {query!r}: {exc}")
            errors += 1
            ranked = []
        ndcgs.append(ndcg_at_k(ranked, judgments, k_ndcg))
        rrs.append(reciprocal_rank(ranked, judgments))
        recalls.append(recall_at_k(ranked, judgments, k_recall))
    return {
        "queries": len(judgments_by_query),
        "errors": errors,
        f"nDCG@{k_ndcg}": mean(ndcgs),
        "MRR": mean(rrs),
        f"recall@{k_recall}": mean(recalls),
    }


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    idx = min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))
    return s[idx]


def docker_stats_sample(container: str) -> dict:
    try:
        out = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.CPUPerc}} {{.MemUsage}}", container],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        cpu, mem = out.split(" ", 1)
        return {"cpu_pct": cpu, "mem_usage": mem}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def run_latency(index, queries: list[str], k: int = 10, warmup: int = 3) -> dict:
    for q in queries[:warmup]:
        try:
            index.search(q, k)
        except Exception:  # noqa: BLE001
            pass
    latencies = []
    for q in queries:
        t0 = time.perf_counter()
        try:
            index.search(q, k)
        except Exception:  # noqa: BLE001
            continue
        latencies.append((time.perf_counter() - t0) * 1000)
    if not latencies:
        return {"queries_measured": 0}
    return {
        "queries_measured": len(latencies),
        "p50_ms": round(_percentile(latencies, 50), 1),
        "p95_ms": round(_percentile(latencies, 95), 1),
        "min_ms": round(min(latencies), 1),
        "max_ms": round(max(latencies), 1),
    }


def main():
    print(f"[bench] loading judgments from {JUDGMENTS_PATH}")
    judgments_by_query = load_judgments()
    print(f"[bench] {len(judgments_by_query)} distinct queries, "
          f"{sum(len(d) for d in judgments_by_query.values())} judgment rows")

    doc_id_to_url_stem = url_relevant_docs(judgments_by_query)
    web_q = web_subset(judgments_by_query)
    print(f"[bench] web-reachable subset: {len(web_q)} queries "
          f"(judged-relevant doc is one of {len(doc_id_to_url_stem)} real crawled URLs)")

    results = {"dimension_A_relevance": {}, "dimension_B_speed": {}}

    # --- Dimension A: relevance ---
    print("\n=== Dimension A: relevance quality ===")
    print("[bench] this-engine, full judgment set...")
    results["dimension_A_relevance"]["this-engine (full set)"] = run_relevance(EngineIndex(), judgments_by_query)
    print(results["dimension_A_relevance"]["this-engine (full set)"])

    if os.environ.get("BENCH_SKIP_OPENSEARCH") != "1":
        try:
            httpx.get(OPENSEARCH_URL, timeout=3.0)
            print("[bench] opensearch, full judgment set...")
            results["dimension_A_relevance"]["opensearch (full set)"] = run_relevance(OpenSearchIndex(), judgments_by_query)
            print(results["dimension_A_relevance"]["opensearch (full set)"])
        except Exception as exc:  # noqa: BLE001
            print(f"[bench] opensearch unreachable, skipping: {exc}")
            results["dimension_A_relevance"]["opensearch"] = {"error": str(exc)}

    print("[bench] searxng, web-reachable subset only...")
    results["dimension_A_relevance"]["searxng (web subset)"] = run_relevance(SearXNGIndex(doc_id_to_url_stem), web_q)
    print(results["dimension_A_relevance"]["searxng (web subset)"])

    results["dimension_A_relevance"]["google-bing"] = {
        "status": "NOT_ATTEMPTED",
        "reason": "no Google Custom Search / Bing API credentials found anywhere on sensalis-node "
                  "(checked env, ~/.anthropic_env, and for a config file) -- same category of blocker "
                  "as P5's Microsoft Graph gap.",
    }

    with open(REPO_ROOT / "data" / "comparative_benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n[bench] Dimension A written -> data/comparative_benchmark_results.json")
    return results


if __name__ == "__main__":
    main()
