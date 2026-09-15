from datetime import datetime
from zoneinfo import ZoneInfo

from app.connectors.microsoft import (
    scan_microsoft,
)


START_DATE = datetime(
    2026,
    8,
    1,
    tzinfo=ZoneInfo(
        "Europe/Paris"
    ),
)


def main() -> None:
    emails = scan_microsoft(
        START_DATE
    )

    print()
    print("=" * 100)

    print(
        f"{len(emails)} mail(s) pertinent(s)"
    )

    print("=" * 100)

    for email in emails:
        print()
        print(email.date)
        print(email.sender)
        print(email.subject)

        print(
            f"Score : {email.score}"
        )

        print(
            f"Statut : {email.status}"
        )

        print(
            f"Message-ID : "
            f"{email.message_id}"
        )


if __name__ == "__main__":
    main()