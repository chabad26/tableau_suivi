from datetime import datetime

from app.connectors.imap import scan_imap
from app.models import DetectedEmail


def scan_external_connectors(
    since: datetime,
    errors: list[str] | None = None,
) -> list[DetectedEmail]:

    try:
        return scan_imap(since)

    except Exception as error:
        print()
        print(
            f"⚠ IMAP indisponible "
            f"({type(error).__name__})"
        )

        if errors is not None:
            errors.append("IMAP")

        return []