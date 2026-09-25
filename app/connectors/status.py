from dataclasses import dataclass

from app.database import (
    get_enabled_imap_accounts,
)


@dataclass
class ConnectorStatus:
    key: str
    name: str
    description: str
    configured: bool
    connected: bool
    status: str


def get_connector_statuses() -> list[ConnectorStatus]:

    accounts = (
        get_enabled_imap_accounts()
    )

    states = {
        str(
            account["last_status"]
            or "unknown"
        )
        for account in accounts
    }

    if not accounts:
        connected = False
        status = "Non configuré"

    elif states == {"connected"}:
        connected = True
        status = (
            f"{len(accounts)} "
            "boîte(s) connectée(s)"
        )

    elif (
        "auth_error" in states
        or "error" in states
    ):
        connected = False
        status = "Attention requise"

    else:
        connected = False
        status = (
            f"{len(accounts)} "
            "boîte(s) à tester"
        )

    return [
        ConnectorStatus(
            key="imap",
            name="Boîtes mail",
            description=(
                "Connexion IMAP unifiée "
                "avec OAuth2 ou mot de passe."
            ),
            configured=bool(accounts),
            connected=connected,
            status=status,
        )
    ]