from __future__ import annotations

import os
from dataclasses import dataclass

from app.connectors.gmail import CREDENTIALS_FILE, TOKEN_FILE
from app.connectors.microsoft import TOKEN_CACHE_FILE


@dataclass
class ConnectorStatus:
    key: str
    name: str
    description: str
    configured: bool
    connected: bool
    status: str


def get_connector_statuses() -> list[ConnectorStatus]:
    gmail_credentials = CREDENTIALS_FILE.exists()

    gmail_token = TOKEN_FILE.exists()

    microsoft_client_id = bool(os.getenv("MICROSOFT_CLIENT_ID", ""))

    microsoft_token = TOKEN_CACHE_FILE.exists()

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
    ]
