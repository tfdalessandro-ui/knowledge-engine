"""Step 7 (Build Kickoff plan): pipeline-config GA search against the P0
harness -- chunk_text already exposed min_tokens/max_tokens/overlap_ratio
params (designed) but ingest.pipeline.run_ingest never overrode them
(never searched). Tests whether tuning document-chunking parameters
improves the P1 BM25-only baseline the P0 harness measures.

RECREATED 2026-09-06 (see LOGBOOK_09062026_*.md, Issue 4 of the
four-issue fix pass): the original run of this script deleted it
afterward, per this project's earlier (now-retired) convention for
one-off tuning scripts. That convention itself was flagged as wrong for
a script whose numeric result is cited in the logbook and the research
loop's candidate registry -- deleting the code that produced a cited
result means it can't be re-run, re-verified, or reused for a future
cycle. Kept permanently in scripts/ from this point on, matching every
other versioned script in this project (seed_corpus.py, benchmark_p2.py,
etc.) -- NOT deleted after use.

For each genome, parses the real corpus once (cached, parsing doesn't
depend on chunk params) then re-chunks + rebuilds a FRESH Tantivy index
in a temp dir per genome (cheap, no embeddings involved -- P0/P1 harness
is BM25-only). Read-only against the live index; writes only to a temp
dir.

Original result (re-verify by simply re-running this script -- that's
the whole point of keeping it):
    BEFORE (defaults 250/400/0.15): nDCG@10 = 0.9091
    AFTER  (GA best: min=142, max=340, overlap=0.007): nDCG@10 = 0.9177
    Relative change: +0.94%
"""
import random
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from config import get_settings
from eval.metrics import mean, ndcg_at_k
from eval.real_index import RealBM25Index
from eval.stub_index import load_judgments
from ingest.chunking import chunk_text, MIN_TOKENS, MAX_TOKENS, OVERLAP_RATIO
from ingest.index_tantivy import BM25Index
from ingest.parsers import SUPPORTED_EXTENSIONS, parse_to_text

settings = get_settings()
all_judgments = load_judgments(settings.judgments_path)
queries = sorted(all_judgments.keys())

print("Parsing corpus once (cached across genomes)...")
parsed = {}
for path in sorted(settings.corpus_dir.iterdir()):
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        continue
    parsed[path.stem] = parse_to_text(path)
print(f"Parsed {len(parsed)} documents.")


def _score_genome(min_tokens, max_tokens, overlap_ratio):
    tmp_dir = Path(tempfile.mkdtemp(prefix="ke_chunk_ga_"))
    try:
        index = BM25Index(tmp_dir / "index")
        for doc_id, text in parsed.items():
            chunks = chunk_text(text, min_tokens=min_tokens, max_tokens=max_tokens, overlap_ratio=overlap_ratio)
            if chunks:
                index.add_chunks(doc_id, chunks)
        index.commit()
        real_index = RealBM25Index(tmp_dir / "index")
        ndcgs = [ndcg_at_k(real_index.search(q, 20), all_judgments[q], 10) for q in queries]
        return mean(ndcgs)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


print(f"\n=== BEFORE: current committed defaults ===")
print(f"min_tokens={MIN_TOKENS} max_tokens={MAX_TOKENS} overlap_ratio={OVERLAP_RATIO}")
baseline_ndcg = _score_genome(MIN_TOKENS, MAX_TOKENS, OVERLAP_RATIO)
print(f"nDCG@10 = {baseline_ndcg:.4f}")


def _random_genome():
    max_t = random.randint(200, 600)
    min_t = random.randint(80, max_t - 20)
    overlap = round(random.uniform(0.0, 0.35), 3)
    return (min_t, max_t, overlap)


def _mutate(genome):
    min_t, max_t, overlap = genome
    choice = random.randint(0, 2)
    if choice == 0:
        min_t = max(50, min(max_t - 20, min_t + random.randint(-40, 40)))
    elif choice == 1:
        max_t = max(min_t + 20, min(700, max_t + random.randint(-60, 60)))
    else:
        overlap = max(0.0, min(0.4, round(overlap + random.uniform(-0.08, 0.08), 3)))
    return (min_t, max_t, overlap)


def _crossover(a, b):
    return (a[0] if random.random() < 0.5 else b[0], a[1] if random.random() < 0.5 else b[1], a[2] if random.random() < 0.5 else b[2])


random.seed(42)
POP, GEN, ELITE = 12, 8, 4
population = [_random_genome() for _ in range(POP)]
population[0] = (MIN_TOKENS, MAX_TOKENS, OVERLAP_RATIO)
cache = {(MIN_TOKENS, MAX_TOKENS, OVERLAP_RATIO): baseline_ndcg}
best_genome, best_fit = (MIN_TOKENS, MAX_TOKENS, OVERLAP_RATIO), baseline_ndcg

print(f"\n=== GA search over (min_tokens, max_tokens, overlap_ratio) ===")
for gen in range(GEN):
    scored = []
    for genome in population:
        if genome not in cache:
            cache[genome] = _score_genome(*genome)
        scored.append((cache[genome], genome))
    scored.sort(key=lambda t: -t[0])
    if scored[0][0] > best_fit:
        best_fit, best_genome = scored[0]
    print(f"gen {gen}: best nDCG@10={scored[0][0]:.4f} genome={scored[0][1]}")
    elites = [g for _, g in scored[:ELITE]]
    next_pop = list(elites)
    while len(next_pop) < POP:
        a, b = random.choice(elites), random.choice(elites)
        child = _crossover(a, b)
        if random.random() < 0.7:
            child = _mutate(child)
        next_pop.append(child)
    population = next_pop

print(f"\n=== RESULT ===")
print(f"BEFORE (defaults {MIN_TOKENS}/{MAX_TOKENS}/{OVERLAP_RATIO}): nDCG@10 = {baseline_ndcg:.4f}")
print(f"AFTER  (GA best {best_genome}): nDCG@10 = {best_fit:.4f}")
delta = (best_fit - baseline_ndcg) / baseline_ndcg
print(f"Relative change: {delta:+.2%}")
print(f"Distinct genomes evaluated: {len(cache)}")
