from datetime import datetime
from zoneinfo import ZoneInfo

from app.connectors.gmail import scan_gmail
from app.settings import API_START_DATE

START_DATE = API_START_DATE


def main() -> None:
    emails = scan_gmail(START_DATE)

    print()
    print("=" * 100)
    print(f"{len(emails)} mail(s) pertinent(s)")
    print("=" * 100)

    for email in emails:
        print()
        print(email.date)

        print(email.sender)

        print(email.subject)

        print(f"Score : {email.score}")

        print(f"Statut : {email.status}")

        print(f"Message-ID : {email.message_id}")


if __name__ == "__main__":
    main()
