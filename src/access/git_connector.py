"""Git connector: ingests files from a local git working directory through
the same BM25/vector pipeline every other corpus document goes through
(`ingest.pipeline.run_ingest`), then registers each file's access control in
`AclStore` from an explicit manifest.

A real enterprise Git connector would read a host's (GitHub/GitLab/Azure
DevOps) collaborator/team API to derive ACLs automatically -- out of scope
without real tenant credentials (see the P5 logbook for why). This connector
takes that mapping as an explicit manifest instead, which is the same shape
of information a real one would produce, just supplied rather than fetched.

Default-deny: a file not mentioned in the manifest gets registered with no
owner and `is_public=False` -- locked down, not silently public. Indexing a
document ahead of its ACL being known is exactly the leakage risk the
roadmap names for this phase; erring toward "nobody can see it yet" is the
safe direction to be wrong in.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from access.acl_store import AclStore
from ingest.pipeline import run_ingest
from ingest.parsers import SUPPORTED_EXTENSIONS


@dataclass
class GitIngestReport:
    documents_ingested: int = 0
    documents_registered: int = 0
    unmanifested_locked_down: list[str] = field(default_factory=list)


def ingest_git_repo(
    repo_dir: Path,
    acl_manifest: dict[str, dict],
    tantivy_dir: Path,
    registry_db: Path,
    acl_store: AclStore,
    vector_index_path: Path | None = None,
    vector_registry_db: Path | None = None,
    manifest_path: Path | None = None,
) -> GitIngestReport:
    """`manifest_path`: if the ACL manifest file itself lives inside
    `repo_dir` (as data/enterprise_demo/acl_manifest.json does), exclude it
    from ingestion -- caught by running this for real: a JSON manifest sitting
    next to its own content otherwise gets scanned and indexed as if it were
    a regular document (harmless, since it defaults to locked-down, but
    noisy and not the intent)."""
    ingest_report = run_ingest(repo_dir, tantivy_dir, registry_db, vector_index_path, vector_registry_db)
    report = GitIngestReport(documents_ingested=ingest_report.added + ingest_report.updated + ingest_report.unchanged)

    for path in sorted(repo_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if manifest_path is not None and path.resolve() == manifest_path.resolve():
            continue

        rel_path = str(path.relative_to(repo_dir))
        doc_id = path.stem
        acl = acl_manifest.get(rel_path)

        if acl is None:
            acl_store.register_document(doc_id, source="git", owner_user_id=None, is_public=False)
            report.unmanifested_locked_down.append(rel_path)
        else:
            acl_store.register_document(
                doc_id, source="git", owner_user_id=acl.get("owner"), is_public=acl.get("public", False)
            )
            for grantee in acl.get("grants", []):
                acl_store.grant(doc_id, grantee)

        report.documents_registered += 1

    return report
