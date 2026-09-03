"""Connector status registry for the P5 spec's five named sources: Git,
SharePoint, OneDrive, Outlook, Teams.

Only Git is implemented (see git_connector.py) -- it needs no OAuth, just a
local working directory. The other four need a real Microsoft Graph API
Azure AD app registration and tenant access, which this project does not
have. Rather than build them against mocked/fake credentials (which would
look connected without being validated against anything real), they're
declared here as NOT_CONFIGURED with an explicit reason -- an honest,
checkable state, same pattern as `ltr.status`'s BLOCKED for P3.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ConnectorStatus:
    name: str
    status: str  # "CONNECTED" | "NOT_CONFIGURED"
    reason: str | None = None


def get_connector_statuses() -> list[ConnectorStatus]:
    return [
        ConnectorStatus("git", "CONNECTED"),
        ConnectorStatus(
            "sharepoint", "NOT_CONFIGURED",
            "needs a real Microsoft Graph API Azure AD app registration + tenant access (not available)",
        ),
        ConnectorStatus(
            "onedrive", "NOT_CONFIGURED",
            "needs a real Microsoft Graph API Azure AD app registration + tenant access (not available)",
        ),
        ConnectorStatus(
            "outlook", "NOT_CONFIGURED",
            "needs a real Microsoft Graph API Azure AD app registration + tenant access (not available)",
        ),
        ConnectorStatus(
            "teams", "NOT_CONFIGURED",
            "needs a real Microsoft Graph API Azure AD app registration + tenant access (not available)",
        ),
    ]


def main() -> int:
    for status in get_connector_statuses():
        line = f"{status.name:12s} {status.status}"
        if status.reason:
            line += f" -- {status.reason}"
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
