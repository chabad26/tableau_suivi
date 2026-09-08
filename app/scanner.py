from datetime import datetime, timezone
from pathlib import Path
import mailbox
from mailrecever import MAILBOXES

from app.models import DetectedEmail
from app.classifier import (
    decode_text,
    parse_date,
    score_message,
    detect_status,
    normalize,
)


START_DATE = datetime(
    2026,
    8,
    1,
    0,
    0,
    0,
    tzinfo=timezone.utc,
)

BLACKLIST_SENDERS = [
    "locservice",
    "locservice.fr",
]


def is_blacklisted_sender(sender: str) -> bool:
    sender_normalized = normalize(sender)

    return any(
        blocked in sender_normalized
        for blocked in BLACKLIST_SENDERS
    )


def scan_mailbox(
    name: str,
    path: Path,
) -> list[DetectedEmail]:

    results: list[DetectedEmail] = []

    if not path.exists():
        print(f"⚠ Boîte introuvable : {path}")
        return results

    mbox = mailbox.mbox(
        str(path),
        create=False,
    )

    scanned = 0
    ignored_old = 0
    ignored_blacklist = 0
    ignored_noise = 0

    for message in mbox:

        scanned += 1

        #
        # DATE
        #
        date = parse_date(
            message.get("Date")
        )

        if date is None:
            continue

        if date.astimezone(timezone.utc) < START_DATE:
            ignored_old += 1
            continue

        #
        # EXPÉDITEUR
        #
        sender = decode_text(
            message.get("From")
        )

        if is_blacklisted_sender(sender):
            ignored_blacklist += 1
            continue

        #
        # DÉTECTION
        #
        score, reasons, body = score_message(
            message
        )

        if score < 4:
            ignored_noise += 1
            continue

        subject = decode_text(
            message.get("Subject")
        )

        status = detect_status(
            subject,
            body,
        )

        results.append(
            DetectedEmail(
                mailbox=name,
                date=date,
                sender=sender,
                subject=subject,
                message_id=decode_text(
                    message.get("Message-ID")
                ),
                score=score,
                status=status,
                reasons=reasons,
                body=body,
            )
        )

    print()
    print(f"📬 {name}")
    print(f"  Mails parcourus : {scanned}")
    print(f"  Trop anciens    : {ignored_old}")
    print(f"  Blacklistés     : {ignored_blacklist}")
    print(f"  Bruit ignoré    : {ignored_noise}")
    print(f"  Détectés        : {len(results)}")

    return results

def scan_all_mailboxes() -> list[DetectedEmail]:

    results: list[DetectedEmail] = []

    for name, path in MAILBOXES.items():
        results.extend(
            scan_mailbox(
                name,
                path,
            )
        )

    results.sort(
        key=lambda email: email.date,
        reverse=True,
    )

    return results
