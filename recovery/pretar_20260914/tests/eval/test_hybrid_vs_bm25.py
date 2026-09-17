"""P2 exit criterion: hybrid (BM25 + vector, RRF-fused) beats BM25-only by a
defined margin (+5% nDCG@10) on the P0/P1 judgment set, over the real
corpus. Builds both indices fresh in a temp directory -- an integration
test by nature, and needs network on first run for the embedding model
(see test_embeddings.py docstring).

MEASURABLY BORDERLINE AFTER THE P6 CORPUS MERGE (2026-09-03, see
LOGBOOK_09032026_142903.md) -- passed comfortably at +6.6% when P2 was
built (BM25=0.8912, hybrid=0.9502) over the original 35-document corpus.
After merging P6's 5 crawled pages into data/corpus/ (an explicit operator
decision, not an accident), the margin narrowed because the crawled
Wikipedia articles on BM25/TF-IDF/HNSW now compete for the same top-k
slots as several judgment-set queries, on both sides of the comparison.

Where this actually lands is itself platform-sensitive right at the
threshold, confirmed by running the SAME test on both machines rather than
assumed: on sensalis-node (Linux, the authoritative execution environment
for this whole project) it measured +6.0% (BM25=0.8739, hybrid=0.9259) --
still passing. On the Windows dev laptop it measured +4.8%
(BM25=0.8748, hybrid=0.9165) -- just under the bar. An earlier version of
this docstring called this a "known regression" and marked the test
`xfail(strict=True)` based on the laptop's number alone; that was wrong --
the laptop has never been this project's authoritative measurement
environment (see HELP.md's repo/execution split), and `strict=True`
correctly caught the mistake by turning the node's unexpected pass into
its own visible failure.

UPDATE 2026-09-03 (second merge, see LOGBOOK_09032026_152832.md): a
second merge the same day (P6 allowlist grown 5->12 URLs, corpus now 47
docs) narrowed the margin further to +0.4% (BM25=0.7924, hybrid=0.7957),
confirmed on sensalis-node itself -- the exit criterion is now genuinely
NOT met on the authoritative environment, not a platform artifact this
time. A real, unrelated FAISS/registry orphan-vector bug was found and
fixed while investigating a discrepancy between this test's number and
the live index's number, but fixing it did NOT rescue the metric -- it
confirmed the failing number was correct all along.

UPDATE 2026-09-03 (judgment set grown, see LOGBOOK_09032026_155830.md):
tried the fix proposed above -- grew the judgment set from 28 to 30
queries (79 to 94 pairs) specifically to cover the 11 of 12 crawled pages
that previously had zero judgment coverage. **This did not fix the
criterion; it made the measured gap worse and changed its sign:**
BM25=0.8477, hybrid=0.8335, **-1.68% relative** -- hybrid now scores
BELOW BM25-only, not just under the 5% bar. The newly-judged crawled
Wikipedia pages are long, keyword-dense pages that BM25's exact
term-frequency scoring rewards very directly for these specific literal
queries; RRF's blending-in of vector-similarity results pulled the fused
top-10 slightly further from the new ground truth than BM25 alone
already was, for this judgment set's current query mix. This is a real
property of the current setup, not a bug -- but it's the opposite of the
prior update's hypothesis, and that miss is itself the finding worth
keeping. **The earlier "growing the judgment set ... is the fix" claim is
retracted as stated.**

UPDATE 2026-09-03 (GA parameter tuning, confirmed to overfit -- see
LOGBOOK_09032026_161900.md): tried a genetic algorithm over `HybridIndex`'s
`rrf_k`/`chunk_fanout` params instead. Against the full 30-query set it
found (rrf_k=1, chunk_fanout=61) scoring +1.97%, an apparent improvement.
**5-fold cross-validation showed this was overfitting**: the GA's
per-fold winners were scattered across the whole search space with no
stable region of agreement, and on held-out queries the GA-selected
params scored WORSE on average (-2.03%) than the plain default (-1.31%).
Not deployed; the live service stays on the library default (60, 100).

UPDATE 2026-09-04 (judgment set grown to 100+ queries, per explicit user
request -- see LOGBOOK_09042026_050500.md): grew the judgment set again,
this time substantially -- 30 to 106 queries, 94 to 221 pairs (every new
grade based on content actually read, not guessed), and correspondingly
raised this file's sibling `test_judgment_set_size` ceiling from 100 to
350 pairs / floor from 10 to 100 queries (a deliberate, documented scope
change, not silent drift). **Result: still fails, essentially unchanged
in sign and magnitude:** -1.61% (BM25=0.9017, hybrid=0.8872) vs. the
30-query set's -1.68% -- a >3x larger judgment set landed in almost
exactly the same place. **This is the most informative result of the
whole investigation:** it makes the original "judgment set is too small"
hypothesis much less credible as the primary driver. The regression looks
like a real property of RRF fusion vs. BM25-alone on this corpus's
current small scale and query mix, not a judgment-set-size artifact.
`xfail(strict=True)` stays in place, reason string kept current below.
Whether a properly cross-validated parameter search (same method as the
GA attempt above, but with ~20+ held-out queries per fold instead of ~6,
now that 106 queries exist) would find something real rather than
overfitting is untested -- a natural next step if pursued, not attempted
in this update to avoid repeating the same mistake at a scale that might
still be too small.

UPDATE 2026-09-04 (round-2 GA + CV with ~21 held-out queries/fold, then
DEPLOYED -- see LOGBOOK_09042026_055006.md): ran the exact next step
proposed above, now that 106 queries exist. Unlike round 1's CV (~6
held-out/fold, confirmed overfitting), this round's GA found `rrf_k=1` as
a STABLE winner in ALL 5 folds (`(1,20) (1,85) (1,22) (1,77) (1,52)` --
`chunk_fanout` varied noisily, `rrf_k` did not), and its held-out
performance genuinely beat the old default: +0.53% avg vs. -1.51% avg.
This is real, validated signal, not overfitting -- confirmed by the
contrast with round 1's result at the same corpus/judgment-set, only with
more held-out data per fold. **Deployed**: `HybridIndex`'s own class
defaults changed from `(chunk_fanout=100, rrf_k=60)` to
`(chunk_fanout=62, rrf_k=1)`, also exposed as `KE_HYBRID_CHUNK_FANOUT`/
`KE_HYBRID_RRF_K` env-configurable `Settings` fields (matching this
project's own env-var-driven config convention) and wired into both
`api/main.py` and `eval.run`'s `--index hybrid` path, so the live service,
this test, and the CLI all now measure/serve the same deployed
configuration. Confirmed live post-restart: `+0.42%` (BM25=0.9017,
hybrid=0.9055) -- hybrid is genuinely ahead of BM25-only again, still
short of +5% but a real, cross-validated improvement over every prior
state in this investigation (which went -1.68% -> -1.61% -> now +0.42%).

UPDATE 2026-09-04 (weighted score fusion beats RRF, DEPLOYED -- see
LOGBOOK_09042026_*.md, the weighted-fusion deploy entry): tried a second
kind of fusion, per an explicit request to try weighted fusion instead of
plain RRF. New module `eval/weighted_fusion.py`: min-max normalizes BM25
and vector scores to [0,1] within each query's own candidate set (RRF
deliberately throws away score magnitude; this keeps it), then combines
as `alpha * norm_bm25 + (1-alpha) * norm_vector`. Unit-tested
(`tests/eval/test_weighted_fusion.py`) and sanity-checked against the real
`HybridIndex` before trusting any CV numbers (alpha=1.0 reproduced
BM25-only nDCG@10 exactly, bit-for-bit). 5-fold CV directly against the
just-deployed RRF config (not the old rrf_k=60 baseline) found weighted
fusion ahead on held-out data in 4/5 folds, average +1.44 to +1.94%
(tested at two different fanout-ceiling widths) vs RRF's +0.56%. `alpha`
converged tightly (0.535-0.548 in 4/5 folds, BOTH widths) -- the real,
stable lever; `chunk_fanout` was noisy across a WIDE range (35-276) with
no clear optimum, i.e. this parameter matters much less than alpha (a
finding only visible after deliberately widening the search space once
the narrower one showed 3/5 folds hugging its ceiling -- a real methodology
lesson: a parameter pinned at its search-space edge means "test a wider
space," not "found the optimum"). **Deployed**: `HybridIndex` gained a
`fusion_mode` param (`"rrf"` | `"weighted"`, default now `"weighted"`) and
an `alpha` param (default `0.535`), both env-configurable
(`KE_HYBRID_FUSION_MODE`, `KE_HYBRID_ALPHA`); `chunk_fanout` default set
to a representative mid-range value (100) since no single value was a
true optimum. **Confirmed live post-restart: +2.66%** (BM25=0.9017,
hybrid=0.9257) -- full trajectory now +6.6% -> +6.0% -> +0.4% -> -1.68%
-> -1.61% -> +0.42% (RRF, rrf_k=1) -> **+2.66% (weighted fusion,
alpha=0.535, current)**. Over 6x the RRF deployment's margin, still short
of +5%. `xfail(strict=True)` stays in place since +5% still isn't met.
"""
from pathlib import Path

import pytest

from config import get_settings
from eval.metrics import mean, ndcg_at_k, reciprocal_rank, recall_at_k
from eval.hybrid_index import HybridIndex
from eval.real_index import RealBM25Index
from eval.stub_index import load_judgments
from ingest.pipeline import run_ingest

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = REPO_ROOT / "data" / "corpus"
JUDGMENTS_PATH = REPO_ROOT / "data" / "judgments" / "judgments.json"
MIN_RELATIVE_IMPROVEMENT = 0.05  # the roadmap's "+5% nDCG@10" exit criterion


def _score(index, judgments_by_query):
    ndcgs, rrs, recalls = [], [], []
    for query, judgments in judgments_by_query.items():
        ranked = index.search(query, k=20)
        ndcgs.append(ndcg_at_k(ranked, judgments, 10))
        rrs.append(reciprocal_rank(ranked, judgments))
        recalls.append(recall_at_k(ranked, judgments, 20))
    return {"nDCG@10": mean(ndcgs), "MRR": mean(rrs), "recall@20": mean(recalls)}


@pytest.fixture(scope="module")
def built_indices(tmp_path_factory):
    tmp_dir = tmp_path_factory.mktemp("hybrid_vs_bm25")
    report = run_ingest(
        CORPUS_DIR,
        tmp_dir / "index",
        tmp_dir / "registry.db",
        vector_index_path=tmp_dir / "vectors" / "index.faiss",
        vector_registry_db=tmp_dir / "vectors.db",
    )
    assert not report.errors, f"ingest errors: {report.errors}"
    assert report.added == report.scanned  # fresh index -- everything is new, nothing skipped as unchanged
    # NOT vectors_added == scanned: that only held by coincidence while every corpus doc
    # produced exactly one chunk. Real crawled pages (P6) can be much longer than the
    # original short synthetic docs and legitimately produce many chunks each -- the real
    # invariant for a fresh build is "at least one chunk per doc", not "exactly one".
    assert report.vectors_added >= report.scanned

    # Built from live Settings (not bare defaults) so this test always
    # reflects whatever scripts/auto_tune.py has most recently deployed
    # via .env, not a stale hardcoded config -- see LOGBOOK_09042026_*.md.
    settings = get_settings()
    bm25_only = RealBM25Index(tmp_dir / "index")
    hybrid = HybridIndex(
        tmp_dir / "index",
        tmp_dir / "vectors" / "index.faiss",
        tmp_dir / "vectors.db",
        chunk_fanout=settings.hybrid_chunk_fanout,
        rrf_k=settings.hybrid_rrf_k,
        fusion_mode=settings.hybrid_fusion_mode,
        alpha=settings.hybrid_alpha,
        alpha_mode=settings.hybrid_alpha_mode,
        alpha_base=settings.hybrid_alpha_base,
        alpha_slope=settings.hybrid_alpha_slope,
    )
    return bm25_only, hybrid


@pytest.mark.xfail(
    reason=(
        "P2 exit criterion (+5% nDCG@10) still NOT met (+2.66% measured on "
        "sensalis-node, 2026-09-04, 47-doc corpus / 106-query judgment set, "
        "weighted-fusion alpha=0.535) -- but genuinely positive and the "
        "best result of the whole investigation, over 6x an earlier "
        "deployed RRF configuration's +0.42%. Two GA+CV rounds led here: "
        "round 1 (rrf_k tuning) found rrf_k=1 stable across 5 folds "
        "(+0.53% held-out avg), deployed first; round 2 (weighted score "
        "fusion vs that deployed RRF baseline) found alpha~0.535-0.548 "
        "stable across 5 folds AND across two different fanout-search-space "
        "widths, beating RRF on held-out data in 4/5 folds -- deployed as "
        "the new default (fusion_mode='weighted'). Full trajectory: +6.6% "
        "-> +6.0% -> +0.4% -> -1.68% -> -1.61% -> +0.42% -> +2.66% "
        "(current). Two earlier fix attempts did NOT hold up (judgment-set "
        "growth alone; a round-1-CV-style GA run with too few held-out "
        "queries/fold, confirmed overfit, never deployed). See "
        "LOGBOOK_09042026_*.md for the full history (multiple entries this "
        "date) and LOGBOOK_09032026_161900.md/_155830.md/_152832.md for "
        "earlier context. strict=True so a future fix surfaces as an "
        "unexpected pass, not silently."
    ),
    strict=True,
)
def test_hybrid_beats_bm25_only_by_5_percent_ndcg10(built_indices):
    bm25_only, hybrid = built_indices
    judgments_by_query = load_judgments(JUDGMENTS_PATH)

    bm25_scores = _score(bm25_only, judgments_by_query)
    hybrid_scores = _score(hybrid, judgments_by_query)

    relative_improvement = (hybrid_scores["nDCG@10"] - bm25_scores["nDCG@10"]) / bm25_scores["nDCG@10"]

    print(f"\nP2 exit criterion: BM25-only nDCG@10={bm25_scores['nDCG@10']:.4f} "
          f"vs hybrid nDCG@10={hybrid_scores['nDCG@10']:.4f} "
          f"({relative_improvement:+.1%} relative)")
    print(f"BM25-only: {bm25_scores}")
    print(f"Hybrid:    {hybrid_scores}")

    assert relative_improvement >= MIN_RELATIVE_IMPROVEMENT, (
        f"hybrid only improved nDCG@10 by {relative_improvement:.1%}, "
        f"below the {MIN_RELATIVE_IMPROVEMENT:.0%} exit criterion"
    )
