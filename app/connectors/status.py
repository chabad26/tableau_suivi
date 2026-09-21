import os
from dataclasses import dataclass

from app.connectors.gmail import CREDENTIALS_FILE, TOKEN_FILE
from app.connectors.microsoft import MICROSOFT_CLIENT_ID, TOKEN_CACHE_FILE
from app.settings import (
    IMAP_ENABLED,
    IMAP_HOST,
    IMAP_PASSWORD,
    IMAP_USERNAME,
)

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

    imap_accounts = get_enabled_imap_accounts()

    legacy_imap_configured = (
        IMAP_ENABLED
        and bool(IMAP_HOST)
        and bool(IMAP_USERNAME)
        and bool(IMAP_PASSWORD)
    )

    imap_configured = (
        bool(imap_accounts)
        or legacy_imap_configured
    )

    imap_status = (
        f"{len(imap_accounts)} boîte(s)"
        if imap_accounts
        else (
            "Configuré"
            if imap_configured
            else "Non configuré"
        )
    )
    
    gmail_credentials = CREDENTIALS_FILE.exists()

    gmail_token = TOKEN_FILE.exists()

    microsoft_client_id = bool(MICROSOFT_CLIENT_ID)

    microsoft_token = TOKEN_CACHE_FILE.exists()
    imap_accounts = (
        get_enabled_imap_accounts()
    )
    imap_status = (
        f"{len(imap_accounts)} boîte(s)"
        if imap_accounts
        else (
            "Configuré"
            if imap_configured
            else "Non configuré"
        )
    )
    return [
        ConnectorStatus(
            key="thunderbird",
            name="Thunderbird",
            description=("Analyse les boîtes mail locales de Thunderbird."),
            configured=True,
            connected=True,
            status="Local",
        ),
        ConnectorStatus(
            key="gmail",
            name="Gmail",
            description=("Connexion à Gmail via OAuth et l'API Google."),
            configured=gmail_credentials,
            connected=(gmail_credentials and gmail_token),
            status=(
                "Connecté"
                if gmail_credentials and gmail_token
                else ("À connecter" if gmail_credentials else "Non configuré")
            ),
        ),
        ConnectorStatus(
            key="microsoft",
            name="Microsoft",
            description=("Connexion à Outlook / Microsoft 365 via Graph."),
            configured=microsoft_client_id,
            connected=(microsoft_client_id and microsoft_token),
            status=(
                "Connecté"
                if microsoft_client_id and microsoft_token
                else ("À connecter" if microsoft_client_id else "Non configuré")
            ),
        ),
        ConnectorStatus(
            key="imap",
            name="IMAP",
            description=(
                "Connexion générique aux boîtes mail "
                "SFR, Orange, Free, OVH et autres fournisseurs."
            ),
            configured=imap_configured,
            connected=imap_configured,
            status=imap_status,
        ),
    ]
