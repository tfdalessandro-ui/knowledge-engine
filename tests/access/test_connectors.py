from access.connectors import get_connector_statuses


def test_git_connector_is_connected():
    statuses = {s.name: s.status for s in get_connector_statuses()}
    assert statuses["git"] == "CONNECTED"


def test_enterprise_connectors_are_honestly_not_configured():
    statuses = {s.name: s.status for s in get_connector_statuses()}
    for name in ("sharepoint", "onedrive", "outlook", "teams"):
        assert statuses[name] == "NOT_CONFIGURED"


def test_not_configured_connectors_have_a_reason():
    for status in get_connector_statuses():
        if status.status == "NOT_CONFIGURED":
            assert status.reason is not None and len(status.reason) > 0
