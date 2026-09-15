from datetime import datetime

from app.connectors.gmail import (
    CREDENTIALS_FILE,
    TOKEN_FILE,
    scan_gmail,
)
from app.models import DetectedEmail


def scan_external_connectors(
    since: datetime,
) -> list[DetectedEmail]:

    emails: list[DetectedEmail] = []

    #
    # Gmail
    #
    # On considère Gmail configuré si on possède
    # soit le client OAuth, soit déjà un token.
    #
    gmail_configured = (
        CREDENTIALS_FILE.exists()
        or TOKEN_FILE.exists()
    )

    if gmail_configured:
        try:
            gmail_emails = scan_gmail(
                since
            )

            emails.extend(
                gmail_emails
            )

        except Exception as error:
            print()
            print(
                "⚠ Gmail indisponible : "
                f"{error}"
            )

    return emails