"""Environment-driven configuration. No hardcoded paths or ports here or anywhere else in this repo."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # env_file anchored to REPO_ROOT, not a bare ".env" (relative-to-cwd) --
    # the live service's WorkingDirectory is src/ while CLI tools
    # (eval.run, pytest) run from the repo root, so a relative path would
    # only ever be found by one of the two. Fixed 2026-09-04 while wiring
    # up scripts/auto_tune.py's deploy mechanism, which needs both to
    # reliably read the same .env. See LOGBOOK_09042026_*.md.
    model_config = SettingsConfigDict(env_prefix="KE_", env_file=str(REPO_ROOT / ".env"), extra="ignore")

    data_dir: Path = REPO_ROOT / "data"
    corpus_dir: Path = REPO_ROOT / "data" / "corpus"
    judgments_path: Path = REPO_ROOT / "data" / "judgments" / "judgments.json"
    registry_db_path: Path = REPO_ROOT / "data" / "registry.db"
    tantivy_index_dir: Path = REPO_ROOT / "data" / "tantivy_index"
    faiss_index_path: Path = REPO_ROOT / "data" / "faiss_index" / "index.faiss"
    vector_registry_db_path: Path = REPO_ROOT / "data" / "vectors.db"
    vector_compact_threshold: float = 0.2  # tombstoned fraction that triggers a FAISS rebuild
    # P2 hybrid fusion params, deployed 2026-09-04 after two rounds of
    # cross-validated GA search (see LOGBOOK_09042026_*.md) -- kept in sync
    # with HybridIndex's own class defaults. fusion_mode="weighted" (score
    # fusion, KE_HYBRID_FUSION_MODE) beat fusion_mode="rrf" (rank fusion)
    # on held-out data in 4/5 folds; hybrid_alpha (KE_HYBRID_ALPHA) is the
    # weighted-fusion weight on the BM25 side, tightly stable across folds
    # (0.535-0.548 in 4/5). hybrid_rrf_k/hybrid_chunk_fanout
    # (KE_HYBRID_RRF_K/KE_HYBRID_CHUNK_FANOUT) are kept for fusion_mode="rrf"
    # (and chunk_fanout is shared by both modes -- it's the candidate-pool
    # depth per side before fusion, not RRF-specific).
    hybrid_rrf_k: int = 1
    hybrid_chunk_fanout: int = 100
    hybrid_fusion_mode: str = "weighted"
    hybrid_alpha: float = 0.535
    # Adaptive alpha (fork point #3): "fixed" uses hybrid_alpha above as a
    # constant; "adaptive" computes alpha per query via eval.adaptive_alpha
    # instead (hybrid_alpha_base/hybrid_alpha_slope, KE_HYBRID_ALPHA_MODE /
    # KE_HYBRID_ALPHA_BASE / KE_HYBRID_ALPHA_SLOPE).
    hybrid_alpha_mode: str = "fixed"
    hybrid_alpha_base: float = 0.535
    hybrid_alpha_slope: float = 0.0
    # Step 8 on-demand discovery (Build Kickoff 2026-09-06): triggered when
    # /search returns fewer than discovery_sparse_threshold hits. Separate
    # index/registry namespace from both the main P1/P2 index and P6's
    # web_tantivy_index_dir -- discovered content is never silently merged
    # into either. No LLM anywhere in this path (see discovery/pipeline.py).
    # discovery_enabled=False fully disables the sparse-trigger check (NOT
    # threshold=0 -- is_sparse([], ...) on an empty top-slice is vacuously
    # True, so threshold=0 would make EVERY query trigger discovery, the
    # opposite of "disabled"; caught live 2026-09-06 before deploying it,
    # see tests/api/test_main.py for why an explicit flag was needed).
    discovery_enabled: bool = True
    discovery_sparse_threshold: int = 2
    discovery_output_dir: Path = REPO_ROOT / "data" / "discovered"
    discovery_provenance_db_path: Path = REPO_ROOT / "data" / "discovery_provenance.db"
    discovery_blocklist_cache_path: Path = REPO_ROOT / "data" / "discovery_blocklist_cache.txt"
    discovered_tantivy_index_dir: Path = REPO_ROOT / "data" / "discovered_tantivy_index"
    discovered_registry_db_path: Path = REPO_ROOT / "data" / "discovered_registry.db"
    discovered_faiss_index_path: Path = REPO_ROOT / "data" / "discovered_faiss_index" / "index.faiss"
    discovered_vector_registry_db_path: Path = REPO_ROOT / "data" / "discovered_vectors.db"
    query_log_db_path: Path = REPO_ROOT / "data" / "query_log.db"
    ltr_min_interactions: int = 500  # roadmap's stated minimum before training a reranker is meaningful
    ltr_model_path: Path = REPO_ROOT / "data" / "ltr_model.txt"
    memgraph_uri: str = "bolt://127.0.0.1:7687"
    # Separate Memgraph instance/port for tests, added 2026-09-14 after the KG
    # test suite's own populated_store fixture was found clear()-ing the live
    # production instance in setup AND teardown (zeroed it for real once, see
    # TODO.md item 5 / LOGBOOK_09142026_*.md). Tests must NEVER point at
    # memgraph_uri above -- a second lightweight container on a different port
    # (memgraph_ke_test, 127.0.0.1:7688) exists specifically so clear() there
    # can never touch production.
    test_memgraph_uri: str = "bolt://127.0.0.1:7688"
    merge_review_db_path: Path = REPO_ROOT / "data" / "merge_review.db"
    postgres_dsn: str = "postgresql://postgres:ke_dev_password@127.0.0.1:5433/knowledge_engine"
    # Separate index namespace from tantivy_index_dir/registry_db_path -- keeps the
    # enterprise_demo content (and its ACLs) out of the index the P1/P2 baseline
    # numbers (nDCG@10 etc.) were recorded against, so those stay reproducible.
    enterprise_tantivy_index_dir: Path = REPO_ROOT / "data" / "enterprise_tantivy_index"
    enterprise_registry_db_path: Path = REPO_ROOT / "data" / "enterprise_registry.db"
    # P6: crawled pages get their own corpus dir + index namespace, same reasoning as
    # P5's enterprise_* split -- keeps ungoverned crawled content out of the index the
    # P1/P2 baseline numbers were recorded against.
    crawl_output_dir: Path = REPO_ROOT / "data" / "crawled"
    crawl_state_db_path: Path = REPO_ROOT / "data" / "crawl_state.db"
    web_tantivy_index_dir: Path = REPO_ROOT / "data" / "web_tantivy_index"
    web_registry_db_path: Path = REPO_ROOT / "data" / "web_registry.db"
    crawl_min_interval_s: float = 3.0
    crawl_politeness_budget_s: float = 60.0
    # Research-to-production loop (Step 2, Build Kickoff 2026-09-06): a
    # SEPARATE crawl target/output/state from the P6 crawl above -- fetched
    # research papers are never merged into the main or web index, they
    # only feed research/loop.py's candidate registry. See
    # research/allowlist.py's own docstring for why this is a distinct
    # list, not an extension of crawl/allowlist.py's P6 allowlist.
    research_crawl_output_dir: Path = REPO_ROOT / "data" / "research_papers"
    research_crawl_state_db_path: Path = REPO_ROOT / "data" / "research_crawl_state.db"
    research_crawl_politeness_budget_s: float = 120.0  # higher than P6's 60s -- arxiv.org's own Crawl-delay is 15s/request, 3 URLs alone can approach 45s
    research_candidates_db_path: Path = REPO_ROOT / "data" / "research_candidates.db"
    # P7: optional, skippable small-LLM answer layer. Not downloaded/managed by this
    # repo -- see HELP.md for the download command. The system is fully usable
    # without this (every P0-P6 feature works with llm_model_path unset).
    llm_model_path: Path = REPO_ROOT / "data" / "models" / "Qwen2.5-3B-Instruct-Q4_K_M.gguf"
    llm_n_ctx: int = 4096
    llm_max_tokens: int = 512
    llm_temperature: float = 0.0  # deterministic-leaning, favors reliable citations over variety
    llm_repeat_penalty: float = 1.3  # 2026-09-08: greedy decoding (temperature=0.0) with a small
    # 3B model was found to degenerate into repeating the same citation token dozens of times
    # until llm_max_tokens cut it off, in 60% of a 20-sample citation-validation batch (see
    # LOGBOOK_09082026_113500.md). llama.cpp's own library default is 1.1; raised here since
    # that default did not prevent the observed loops. Not GA-tuned -- see truncate_on_repeat()
    # in answer/model.py for the actual safety net this relies on.
    bench_log_dir: Path = REPO_ROOT / "data" / "bench_logs"
    host: str = "127.0.0.1"
    port: int = 8000


def get_settings() -> Settings:
    return Settings()
