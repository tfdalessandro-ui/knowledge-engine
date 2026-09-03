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
    bench_log_dir: Path = REPO_ROOT / "data" / "bench_logs"
    host: str = "127.0.0.1"
    port: int = 8000


def get_settings() -> Settings:
    return Settings()
