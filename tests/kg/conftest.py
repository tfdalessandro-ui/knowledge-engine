"""Memgraph is external infrastructure (a Docker container), not an
embedded library like Tantivy/FAISS -- unlike every prior phase, `pytest -q`
genuinely cannot exercise this code on a machine without it running. Tests
marked `@pytest.mark.requires_memgraph` (or carrying a module-level
`pytestmark = pytest.mark.requires_memgraph`) are auto-skipped with a clear
reason when it's unreachable, rather than erroring -- so the "single
documented command" still passes cleanly on a machine with no Memgraph
(e.g. this repo's dev laptop, which has no Docker daemon running) while
running for real wherever Memgraph is up (e.g. sensalis-node).
"""
import pytest

from config import get_settings


def _memgraph_reachable() -> bool:
    # Checks test_memgraph_uri (127.0.0.1:7688), not memgraph_uri (production,
    # 127.0.0.1:7687) -- every test in this package now runs against the
    # isolated test instance (see TODO.md item 5), so that's the one that
    # actually needs to be up for these tests to be meaningful.
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(get_settings().test_memgraph_uri, auth=None)
        with driver.session() as session:
            session.run("RETURN 1").consume()
        driver.close()
        return True
    except Exception:  # noqa: BLE001 - any connection failure means "not reachable"
        return False


_REACHABLE = _memgraph_reachable()  # checked once per test session, not per test


def pytest_configure(config):
    config.addinivalue_line("markers", "requires_memgraph: needs a running Memgraph instance")


def pytest_collection_modifyitems(config, items):
    if _REACHABLE:
        return
    skip = pytest.mark.skip(reason="Memgraph not reachable at KE_MEMGRAPH_URI -- see HELP.md for the docker run command")
    for item in items:
        if "requires_memgraph" in item.keywords:
            item.add_marker(skip)
