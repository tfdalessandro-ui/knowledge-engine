"""Environment-driven configuration. No hardcoded paths or ports here or anywhere else in this repo."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KE_", env_file=".env", extra="ignore")

    data_dir: Path = REPO_ROOT / "data"
    corpus_dir: Path = REPO_ROOT / "data" / "corpus"
    judgments_path: Path = REPO_ROOT / "data" / "judgments" / "judgments.json"
    registry_db_path: Path = REPO_ROOT / "data" / "registry.db"
    tantivy_index_dir: Path = REPO_ROOT / "data" / "tantivy_index"
    faiss_index_path: Path = REPO_ROOT / "data" / "faiss_index" / "index.faiss"
    vector_registry_db_path: Path = REPO_ROOT / "data" / "vectors.db"
    vector_compact_threshold: float = 0.2  # tombstoned fraction that triggers a FAISS rebuild
    query_log_db_path: Path = REPO_ROOT / "data" / "query_log.db"
    ltr_min_interactions: int = 500  # roadmap's stated minimum before training a reranker is meaningful
    ltr_model_path: Path = REPO_ROOT / "data" / "ltr_model.txt"
    memgraph_uri: str = "bolt://127.0.0.1:7687"
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
    # P7: optional, skippable small-LLM answer layer. Not downloaded/managed by this
    # repo -- see HELP.md for the download command. The system is fully usable
    # without this (every P0-P6 feature works with llm_model_path unset).
    llm_model_path: Path = REPO_ROOT / "data" / "models" / "Qwen2.5-3B-Instruct-Q4_K_M.gguf"
    llm_n_ctx: int = 4096
    llm_max_tokens: int = 512
    llm_temperature: float = 0.0  # deterministic-leaning, favors reliable citations over variety
    bench_log_dir: Path = REPO_ROOT / "data" / "bench_logs"
    host: str = "127.0.0.1"
    port: int = 8000


def get_settings() -> Settings:
    return Settings()
