from datetime import datetime

from app.connectors.base import ConnectorSpec
from app.connectors.gmail import CREDENTIALS_FILE, TOKEN_FILE, scan_gmail
from app.connectors.microsoft import MICROSOFT_CLIENT_ID, scan_microsoft
from app.models import DetectedEmail
from app.connectors.imap import (
    scan_imap,
)
from app.settings import (
    IMAP_ENABLED,
    IMAP_HOST,
    IMAP_PASSWORD,
    IMAP_USERNAME,
)

def scan_external_connectors(
    since: datetime, errors: list[str] | None = None
) -> list[DetectedEmail]:

    emails: list[DetectedEmail] = []

    # L'ordre reste Gmail puis Microsoft. L'échec d'une source n'arrête pas les autres.
    connectors = (
        ConnectorSpec(
            "Gmail", CREDENTIALS_FILE.exists() or TOKEN_FILE.exists(), scan_gmail
        ),
        ConnectorSpec("Microsoft", bool(MICROSOFT_CLIENT_ID), scan_microsoft),
        ConnectorSpec(
            "IMAP",
            (
                IMAP_ENABLED
                and bool(IMAP_HOST)
                and bool(IMAP_USERNAME)
                and bool(IMAP_PASSWORD)
            ),
            scan_imap,
        ),
    )
    for connector in connectors:
        if not connector.configured:
            continue
        try:
            emails.extend(connector.scan(since))
        except Exception as error:
            print()
            print(f"⚠ {connector.name} indisponible ({type(error).__name__})")
            if errors is not None:
                errors.append(connector.name)

    return emails
