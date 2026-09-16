from app.connectors.imap import (
    scan_imap,
)
from app.settings import (
    API_START_DATE,
)


emails = scan_imap(
    API_START_DATE
)

print()
print(
    f"{len(emails)} mail(s) pertinent(s)"
)

for mail in emails:
    print()
    print(mail.date)
    print(mail.sender)
    print(mail.subject)
    print(mail.status)

    print("Raisons :", mail.reasons)

    print(
        "Corps :",
        mail.body[:1000]
        .replace("\n", " ")
    )