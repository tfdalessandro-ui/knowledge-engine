"""Runs answer.pipeline over a fixed 20-query sample for the Step 5 P7
citation-validation expansion (was 3 queries, now 20). Writes each
query's full answer + citations to a JSON file for manual side-by-side
review against the real source text afterward.

RE-RUN 2026-09-15 (LOGBOOK_09152026_092024.md): recovered from the
pre-migration backup (never committed to git, same repo/execution-split
symptom as scripts/weighted_fusion.py) to get a real, current citation
number after fixing the prompt bug that caused the "[chunk_id bm25::0]"
malformed-citation failures. Two changes from the original: (1) dropped
alpha_mode/alpha_base/alpha_slope from the HybridIndex(...) call --
adaptive alpha was never reimplemented when weighted_fusion.py was
recovered (TODO.md item 10), current HybridIndex doesn't accept those
kwargs; (2) OUT_PATH points at a new, dated file rather than overwriting
data/p7_20query_batch_results.json (the original 2026-09-07 run,
80/80 chunk-id-validity, kept as-is for comparison) -- resuming against
the OLD file would have skipped all 20 queries as "already done" and
produced nothing new.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "src")

from answer.pipeline import AnswerEngine  # noqa: E402
from config import get_settings  # noqa: E402
from eval.hybrid_index import HybridIndex  # noqa: E402

settings = get_settings()
index = HybridIndex(
    settings.tantivy_index_dir,
    settings.faiss_index_path,
    settings.vector_registry_db_path,
    chunk_fanout=settings.hybrid_chunk_fanout,
    rrf_k=settings.hybrid_rrf_k,
    fusion_mode=settings.hybrid_fusion_mode,
    alpha=settings.hybrid_alpha,
)
engine = AnswerEngine(index, settings.llm_model_path, n_ctx=settings.llm_n_ctx, max_tokens=settings.llm_max_tokens, temperature=settings.llm_temperature)

QUERIES = [
    "8-bit integer quantization for faster cpu inference",
    "a spreadsheet documenting benchmark latency results",
    "best metric when a user only needs one correct answer",
    "combining bm25 score vector score click history and freshness signals",
    "crawler responsibility is discovery not ranking",
    "document chunking for indexing",
    "first relevant result rank scoring for question answering",
    "highlighting matched phrases in full text search results",
    "hybrid search combining keyword and vector",
    "layered proximity graph structure for nearest neighbor search",
    "merging lexical and semantic ranked result lists",
    "openapi documentation generated from type annotations",
    "pip freeze for a reproducible requirements file",
    "python virtual environment versus the system python install",
    "reducing neural network weight precision for cpu speed",
    "roadmap phases and hard gates",
    "separating what gets indexed from how it gets ranked",
    "starlette and pydantic used together in a web framework",
    "the bm25 auxiliary function inside sqlite full text search",
    "vcpu ram and disk specs compared across servers",
]

OUT_PATH = Path("data/p7_20query_batch_results_20260915.json")
results = json.loads(OUT_PATH.read_text()) if OUT_PATH.exists() else {}

for i, q in enumerate(QUERIES):
    if q in results:
        print(f"[{i+1}/20] already done: {q}")
        continue
    t0 = time.time()
    result = engine.answer(q)
    elapsed = time.time() - t0
    results[q] = {
        "answer_text": result.answer_text,
        "retrieved_chunk_ids": result.retrieved_chunk_ids,
        "citations_found": result.citation_check.citations_found,
        "valid_citations": result.citation_check.valid_citations,
        "invalid_citations": result.citation_check.invalid_citations,
        "elapsed_s": elapsed,
    }
    OUT_PATH.write_text(json.dumps(results, indent=2, default=str))
    print(f"[{i+1}/20] done in {elapsed:.0f}s: {q}")

print("ALL DONE")
