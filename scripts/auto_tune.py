"""Recurring GA parameter search for P2's hybrid fusion, with a permanent
held-out gate and auto-deploy. Cron'd daily (OSE_AUTO_TUNE) so the live
service keeps re-optimizing as the corpus/judgment set changes, without
needing a human to re-run this investigation by hand each time.

DESIGN, and why each piece exists (see LOGBOOK_09042026_*.md for the full
investigation this formalizes):

- Skip entirely if neither the corpus nor the judgment set has changed
  since the last run (a content hash in data/auto_tune_state.json) --
  otherwise a daily cron would re-run an expensive GA for no reason on a
  system where corpus/judgment growth is a deliberate, infrequent,
  manual act.
- PERMANENT held-out split: a query's fold assignment is a deterministic
  hash of the query text itself (not a random per-run shuffle), so the
  held-out set used to decide whether to deploy is stable across runs and
  can't be gamed or drift by chance -- fork point #6 from
  LOGBOOK_09042026_060353.md, implemented here rather than left
  unexplored, specifically because auto-deploy needs a trustworthy gate
  more than manual runs did.
- The GA optimizes ONLY on the non-held-out ("tuning pool") queries. The
  held-out set is NEVER touched during optimization -- it's used exactly
  once per run, to compare the GA's champion against whatever is
  currently deployed, on data neither has been tuned against.
- Deploy only if the champion beats the currently-deployed config on the
  held-out set by a real margin (DEPLOY_MARGIN), not just numerically --
  avoids flapping the live service on noise between two nearly-identical
  configs.
- Deploy mechanism: writes OSE_HYBRID_* into REPO_ROOT/.env (the anchored
  path both the live service and CLI tools read, see config/__init__.py's
  2026-09-04 fix), restarts the systemd unit, and verifies health + a
  real query before considering the deploy successful. Any verification
  failure triggers an automatic rollback to the previous .env and a
  second restart+verify.
- Writes a full LOGBOOK_*.md entry every time it actually runs a search
  (deploy or not) -- per the standing "always log findings" rule. A
  skipped run (nothing changed) only appends one line to
  AUTO_TUNE_LOG.md, not a full logbook entry, to keep the logbook signal
  meaningful rather than one entry per day forever.
"""
from __future__ import annotations

import hashlib
import json
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from config import get_settings, REPO_ROOT  # noqa: E402
from eval.adaptive_alpha import adaptive_alpha  # noqa: E402
from eval.fusion import rrf_scores  # noqa: E402
from eval.metrics import mean, ndcg_at_k  # noqa: E402
from eval.stub_index import load_judgments  # noqa: E402
from eval.weighted_fusion import weighted_fusion_scores  # noqa: E402
from ingest.embeddings import embed_texts  # noqa: E402
from ingest.index_faiss import VectorIndex  # noqa: E402
from ingest.index_tantivy import BM25Index  # noqa: E402
from ingest.vector_registry import VectorRegistry  # noqa: E402

STATE_PATH = REPO_ROOT / "data" / "auto_tune_state.json"
ROLL_LOG_PATH = REPO_ROOT / "AUTO_TUNE_LOG.md"
ENV_PATH = REPO_ROOT / ".env"
MAX_FANOUT = 340
DEPLOY_MARGIN = 0.005  # 0.5 percentage points of relative improvement -- must clear this to redeploy, not just numerically edge ahead
K_HOLDOUT_MOD = 5  # 1/5 of queries, deterministically, are permanent holdout


def _content_hash(settings) -> str:
    h = hashlib.sha256()
    for p in sorted(settings.corpus_dir.iterdir()):
        h.update(f"{p.name}:{p.stat().st_size}:{int(p.stat().st_mtime)}".encode())
    h.update(settings.judgments_path.read_bytes())
    return h.hexdigest()


def _is_holdout(query: str) -> bool:
    return int(hashlib.md5(query.encode()).hexdigest(), 16) % K_HOLDOUT_MOD == 0


def _collapse_best_score(hits_iter):
    ordered, best = [], {}
    for doc_id, score in hits_iter:
        if doc_id not in best:
            ordered.append(doc_id)
            best[doc_id] = score
    return ordered, best


def _precompute(settings, queries):
    bm25_index = BM25Index(settings.tantivy_index_dir)
    vector_index = VectorIndex(settings.faiss_index_path)
    vector_registry = VectorRegistry(settings.vector_registry_db_path)
    out = {}
    for q in queries:
        bm25_hits = bm25_index.search(q, limit=MAX_FANOUT)
        bm25_ordered, bm25_best = _collapse_best_score((h.doc_id, h.score) for h in bm25_hits)
        query_vector = embed_texts([q])[0]
        scores, ids = vector_index.search(query_vector, MAX_FANOUT)
        valid_ids = [int(x) for x in ids if x != -1]
        records = vector_registry.get_active_by_ids(valid_ids)
        score_by_id = dict(zip((int(x) for x in ids), scores))
        vec_ordered, vec_best = _collapse_best_score(
            (records[vid].doc_id, float(score_by_id[vid])) for vid in valid_ids if vid in records
        )
        out[q] = {"bm25_ordered": bm25_ordered, "bm25_best": bm25_best, "vec_ordered": vec_ordered, "vec_best": vec_best}
    return out


def _score_genome(precomputed, judgments, genome, query_subset):
    ndcgs = []
    for q in query_subset:
        p = precomputed[q]
        fanout = genome["chunk_fanout"]
        bm25_ranking = p["bm25_ordered"][:fanout]
        vec_ranking = p["vec_ordered"][:fanout]
        if genome["fusion_mode"] == "rrf":
            scores, _ = rrf_scores([bm25_ranking, vec_ranking], k=genome["rrf_k"])
        else:
            bm25_sub = {d: p["bm25_best"][d] for d in bm25_ranking}
            vec_sub = {d: p["vec_best"][d] for d in vec_ranking}
            if genome["alpha_mode"] == "adaptive":
                alpha = adaptive_alpha(q, genome["alpha_base"], genome["alpha_slope"])
            else:
                alpha = genome["alpha"]
            scores = weighted_fusion_scores(bm25_sub, vec_sub, alpha=alpha)
        fused = sorted(scores, key=lambda d: -scores[d])[:20]
        ndcgs.append(ndcg_at_k(fused, judgments[q], 10))
    return mean(ndcgs)


def _bm25_only_ndcg(precomputed, judgments, query_subset):
    ndcgs = [ndcg_at_k(precomputed[q]["bm25_ordered"], judgments[q], 10) for q in query_subset]
    return mean(ndcgs)


def _relative_improvement(hybrid, bm25):
    return (hybrid - bm25) / bm25


def _random_genome():
    fusion_mode = random.choice(["rrf", "weighted"])
    alpha_mode = random.choice(["fixed", "adaptive"])
    return {
        "fusion_mode": fusion_mode,
        "rrf_k": random.randint(1, 200),
        "chunk_fanout": random.randint(20, MAX_FANOUT),
        "alpha_mode": alpha_mode,
        "alpha": round(random.uniform(0.0, 1.0), 3),
        "alpha_base": round(random.uniform(0.0, 1.0), 3),
        "alpha_slope": round(random.uniform(-1.0, 1.0), 3),
    }


def _mutate(genome):
    g = dict(genome)
    field = random.choice(list(g.keys()))
    if field == "fusion_mode":
        g["fusion_mode"] = "rrf" if g["fusion_mode"] == "weighted" else "weighted"
    elif field == "rrf_k":
        g["rrf_k"] = max(1, min(200, g["rrf_k"] + random.randint(-30, 30)))
    elif field == "chunk_fanout":
        g["chunk_fanout"] = max(20, min(MAX_FANOUT, g["chunk_fanout"] + random.randint(-50, 50)))
    elif field == "alpha_mode":
        g["alpha_mode"] = "fixed" if g["alpha_mode"] == "adaptive" else "adaptive"
    elif field == "alpha":
        g["alpha"] = max(0.0, min(1.0, round(g["alpha"] + random.uniform(-0.15, 0.15), 3)))
    elif field == "alpha_base":
        g["alpha_base"] = max(0.0, min(1.0, round(g["alpha_base"] + random.uniform(-0.15, 0.15), 3)))
    elif field == "alpha_slope":
        g["alpha_slope"] = max(-1.0, min(1.0, round(g["alpha_slope"] + random.uniform(-0.2, 0.2), 3)))
    return g


def _crossover(a, b):
    return {k: (a[k] if random.random() < 0.5 else b[k]) for k in a}


def _genome_key(g):
    return tuple(g[k] for k in sorted(g))


def _run_ga(precomputed, judgments, tuning_queries, pop_size=24, generations=18, elite=6, seed=42):
    random.seed(seed)
    tuning_bm25 = _bm25_only_ndcg(precomputed, judgments, tuning_queries)
    population = [_random_genome() for _ in range(pop_size)]
    cache = {}
    best_genome, best_fit = None, -1
    for _gen in range(generations):
        scored = []
        for genome in population:
            key = _genome_key(genome)
            if key not in cache:
                cache[key] = (genome, _score_genome(precomputed, judgments, genome, tuning_queries))
            scored.append(cache[key])
        scored.sort(key=lambda t: -t[1])
        if scored[0][1] > best_fit:
            best_genome, best_fit = scored[0]
        elites = [g for g, _ in scored[:elite]]
        next_pop = list(elites)
        while len(next_pop) < pop_size:
            a, b = random.choice(elites), random.choice(elites)
            child = _crossover(a, b)
            if random.random() < 0.7:
                child = _mutate(child)
            next_pop.append(child)
        population = next_pop
    return best_genome, best_fit, tuning_bm25, len(cache)


def _current_deployed_genome(settings):
    return {
        "fusion_mode": settings.hybrid_fusion_mode,
        "rrf_k": settings.hybrid_rrf_k,
        "chunk_fanout": settings.hybrid_chunk_fanout,
        "alpha_mode": settings.hybrid_alpha_mode,
        "alpha": settings.hybrid_alpha,
        "alpha_base": settings.hybrid_alpha_base,
        "alpha_slope": settings.hybrid_alpha_slope,
    }


def _env_lines_for(genome) -> str:
    return "\n".join([
        f"OSE_HYBRID_FUSION_MODE={genome['fusion_mode']}",
        f"OSE_HYBRID_RRF_K={genome['rrf_k']}",
        f"OSE_HYBRID_CHUNK_FANOUT={genome['chunk_fanout']}",
        f"OSE_HYBRID_ALPHA_MODE={genome['alpha_mode']}",
        f"OSE_HYBRID_ALPHA={genome['alpha']}",
        f"OSE_HYBRID_ALPHA_BASE={genome['alpha_base']}",
        f"OSE_HYBRID_ALPHA_SLOPE={genome['alpha_slope']}",
    ]) + "\n"


def _deploy(genome) -> tuple[bool, str]:
    """Writes .env, restarts the service, verifies health + a real query.
    Rolls back automatically on any verification failure. Returns
    (success, detail_message)."""
    settings = get_settings()
    base = settings.api_base_url
    previous_env = ENV_PATH.read_text() if ENV_PATH.exists() else ""
    backup_path = ENV_PATH.with_suffix(f".bak_{int(time.time())}")
    if ENV_PATH.exists():
        backup_path.write_text(previous_env)

    ENV_PATH.write_text(_env_lines_for(genome))
    restart = subprocess.run(
        ["systemctl", "--user", "restart", settings.service_name],
        capture_output=True, text=True,
    )
    if restart.returncode != 0:
        ENV_PATH.write_text(previous_env)
        return False, f"restart command failed: {restart.stderr.strip()} -- rolled back .env"

    time.sleep(3)
    health = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", f"{base}/health"], capture_output=True, text=True)
    query_check = subprocess.run(
        ["curl", "-s", "-G", f"{base}/search", "--data-urlencode", f"q={settings.smoke_query}", "--data", "k=3"],
        capture_output=True, text=True,
    )
    ok = health.stdout.strip() == "200" and '"hits"' in query_check.stdout and query_check.stdout.count('"doc_id"') > 0
    if not ok:
        ENV_PATH.write_text(previous_env)
        subprocess.run(["systemctl", "--user", "restart", settings.service_name], capture_output=True, text=True)
        time.sleep(3)
        rollback_health = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", f"{base}/health"], capture_output=True, text=True)
        return False, (
            f"post-deploy verification FAILED (health={health.stdout.strip()!r}, "
            f"query had hits: {'\"doc_id\"' in query_check.stdout}) -- rolled back .env "
            f"and restarted; rollback health check: {rollback_health.stdout.strip()!r}"
        )
    return True, f"verified live: health=200, real query returned real hits"


def main():
    settings = get_settings()
    now = datetime.now(timezone.utc)
    ts = now.strftime("%m%d%Y_%H%M%S")

    current_hash = _content_hash(settings)
    state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}
    if state.get("last_hash") == current_hash:
        with ROLL_LOG_PATH.open("a") as f:
            f.write(f"- {now.isoformat()}: skipped, no corpus/judgment change since last run\n")
        print("No change detected -- skipped.")
        return

    all_judgments = load_judgments(settings.judgments_path)
    queries = sorted(all_judgments.keys())
    holdout_queries = [q for q in queries if _is_holdout(q)]
    tuning_queries = [q for q in queries if not _is_holdout(q)]

    print(f"Precomputing candidates for {len(queries)} queries "
          f"({len(tuning_queries)} tuning, {len(holdout_queries)} permanent holdout)...")
    precomputed = _precompute(settings, queries)

    champion, tuning_fit, tuning_bm25, n_evaluated = _run_ga(precomputed, all_judgments, tuning_queries)
    tuning_rel = _relative_improvement(tuning_fit, tuning_bm25)

    holdout_bm25 = _bm25_only_ndcg(precomputed, all_judgments, holdout_queries)
    champion_holdout_fit = _score_genome(precomputed, all_judgments, champion, holdout_queries)
    champion_holdout_rel = _relative_improvement(champion_holdout_fit, holdout_bm25)

    deployed_genome = _current_deployed_genome(settings)
    deployed_holdout_fit = _score_genome(precomputed, all_judgments, deployed_genome, holdout_queries)
    deployed_holdout_rel = _relative_improvement(deployed_holdout_fit, holdout_bm25)

    will_deploy = champion_holdout_rel >= deployed_holdout_rel + DEPLOY_MARGIN
    deploy_success, deploy_detail = (None, "not attempted -- champion did not clear the deploy margin")
    if will_deploy:
        deploy_success, deploy_detail = _deploy(champion)

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps({
        "last_hash": current_hash,
        "last_run": now.isoformat(),
        "deployed_genome": champion if (will_deploy and deploy_success) else deployed_genome,
    }, indent=2))

    log_path = REPO_ROOT / f"LOGBOOK_{ts}.md"
    log_path.write_text(f"""# Logbook — auto_tune.py run ({now.strftime('%Y-%m-%d %H:%M UTC')})

Automated recurring GA search (`scripts/auto_tune.py`, cron `OSE_AUTO_TUNE`).
Corpus/judgment-set content changed since the last run (hash differs), so
this ran a real search rather than skipping.

## Setup
- {len(queries)} total queries: {len(tuning_queries)} tuning pool, {len(holdout_queries)} permanent holdout (deterministic hash-based split, stable across runs).
- GA evaluated {n_evaluated} distinct genomes on the tuning pool only.

## Result
- Tuning-pool (in-sample) champion: `{champion}` -- rel. improvement {tuning_rel:+.2%}
- **Held-out (never used for tuning) -- champion: {champion_holdout_rel:+.2%} | currently deployed: {deployed_holdout_rel:+.2%}**
- Deploy margin required: {DEPLOY_MARGIN:+.2%}
- Decision: {"DEPLOY (champion cleared the margin)" if will_deploy else "NO DEPLOY (champion did not beat the deployed config by enough on held-out data)"}
{f"- Deploy outcome: {'SUCCESS' if deploy_success else 'FAILED, ROLLED BACK'} -- {deploy_detail}" if will_deploy else ""}

## Currently deployed config (baseline for this comparison)
`{deployed_genome}`

## Champion config
`{champion}`
""")
    print(f"Logged: {log_path}")
    print(f"Held-out: champion={champion_holdout_rel:+.2%} deployed={deployed_holdout_rel:+.2%} -> "
          f"{'DEPLOYED' if will_deploy and deploy_success else 'not deployed'}")


if __name__ == "__main__":
    main()
