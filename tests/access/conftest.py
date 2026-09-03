"""PostgreSQL is external infrastructure (a Docker container), same
situation as Memgraph in tests/kg/conftest.py -- tests marked
`pytestmark = pytest.mark.requires_postgres` are auto-skipped with a clear
reason when it's unreachable, so `pytest -q` stays clean on a machine
without it (this repo's dev laptop) while running for real wherever it's up
(sensalis-node).
"""
import pytest

from config import get_settings


def _postgres_reachable() -> bool:
    try:
        import psycopg

        conn = psycopg.connect(get_settings().postgres_dsn, connect_timeout=3)
        conn.close()
        return True
    except Exception:  # noqa: BLE001 - any connection failure means "not reachable"
        return False


_REACHABLE = _postgres_reachable()


def pytest_configure(config):
    config.addinivalue_line("markers", "requires_postgres: needs a running PostgreSQL instance")


def pytest_collection_modifyitems(config, items):
    if _REACHABLE:
        return
    skip = pytest.mark.skip(reason="PostgreSQL not reachable at KE_POSTGRES_DSN -- see HELP.md for the docker run command")
    for item in items:
        if "requires_postgres" in item.keywords:
            item.add_marker(skip)
