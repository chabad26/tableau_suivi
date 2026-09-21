from dataclasses import dataclass
from app.connectors.gmail import CREDENTIALS_FILE, TOKEN_FILE
from app.connectors.microsoft import MICROSOFT_CLIENT_ID, TOKEN_CACHE_FILE
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

    imap_configured = bool(imap_accounts)

    imap_states = {
        str(account["last_status"] or "unknown")
        for account in imap_accounts
    }

    if not imap_accounts:
        imap_connected = False
        imap_status = "Non configuré"

    elif imap_states == {"connected"}:
        imap_connected = True
        imap_status = (
            f"{len(imap_accounts)} boîte(s) connectée(s)"
        )

    elif "auth_error" in imap_states or "error" in imap_states:
        imap_connected = False
        imap_status = "Attention requise"

    else:
        imap_connected = False
        imap_status = (
            f"{len(imap_accounts)} boîte(s) à tester"
        )
    
    gmail_credentials = CREDENTIALS_FILE.exists()

    gmail_token = TOKEN_FILE.exists()

    microsoft_client_id = bool(MICROSOFT_CLIENT_ID)

    microsoft_token = TOKEN_CACHE_FILE.exists()
    return [
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
            connected=imap_connected,
            status=imap_status,
        ),
    ]
