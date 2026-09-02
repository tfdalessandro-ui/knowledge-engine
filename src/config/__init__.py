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
    bench_log_dir: Path = REPO_ROOT / "data" / "bench_logs"
    host: str = "127.0.0.1"
    port: int = 8000


def get_settings() -> Settings:
    return Settings()
