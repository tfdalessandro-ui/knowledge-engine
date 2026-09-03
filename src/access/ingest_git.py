"""CLI: ingest a local git working directory + ACL manifest.

Run: PYTHONPATH=src .venv/bin/python -m access.ingest_git --repo data/enterprise_demo --manifest data/enterprise_demo/acl_manifest.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from access.acl_store import AclStore
from access.git_connector import ingest_git_repo
from config import get_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest a local git repo with an ACL manifest")
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)

    settings = get_settings()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))

    with AclStore(settings.postgres_dsn) as store:
        # Deliberately the enterprise_* index, NOT tantivy_index_dir/registry_db_path --
        # keeps this content out of the index the P1/P2 baseline numbers were recorded
        # against. No vector index either: P5's scope is the ACL mechanism, not hybrid
        # search over enterprise content.
        report = ingest_git_repo(
            args.repo, manifest, settings.enterprise_tantivy_index_dir, settings.enterprise_registry_db_path, store,
            manifest_path=args.manifest,
        )

    print(f"documents_ingested={report.documents_ingested} documents_registered={report.documents_registered}")
    if report.unmanifested_locked_down:
        print(f"locked down (no manifest entry): {report.unmanifested_locked_down}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
