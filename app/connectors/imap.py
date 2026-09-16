from __future__ import annotations

import email
import imaplib
import ssl
import time

from datetime import datetime, timezone
from email.message import Message
from email.utils import parsedate_to_datetime

from app.classifier import (
    detect_status,
    score_message,
)
from app.mail_filters import (
    should_analyze_email,
)
from app.models import DetectedEmail
from app.settings import (
    IMAP_FOLDER,
    IMAP_HOST,
    IMAP_PASSWORD,
    IMAP_PORT,
    IMAP_USERNAME,
)
from app.connectors.common import (
    build_email_message,
    decode_mime_header,
    html_to_text,

)

def get_message_body(
    message: Message,
) -> str:
    if message.is_multipart():
        plain_parts: list[str] = []
        html_parts: list[str] = []

        for part in message.walk():
            disposition = str(
                part.get(
                    "Content-Disposition",
                    "",
                )
            ).casefold()

            if "attachment" in disposition:
                continue

            content_type = part.get_content_type()

            if content_type not in {
                "text/plain",
                "text/html",
            }:
                continue

            payload = part.get_payload(
                decode=True
            )

            # get_payload peut aussi renvoyer un Message : decode exige des octets.
            if not isinstance(payload, bytes) or not payload:
                continue

            charset = (
                part.get_content_charset()
                or "utf-8"
            )

            text = payload.decode(
                charset,
                errors="replace",
            )

            if content_type == "text/plain":
                plain_parts.append(text)
            else:
                html_parts.append(text)

        if plain_parts:
            return "\n\n".join(
                plain_parts
            ).strip()

        if html_parts:
            return html_to_text(
                "\n\n".join(
                    html_parts
                )
            )

        return ""

    payload = message.get_payload(
        decode=True
    )

    if not isinstance(payload, bytes) or not payload:
        return ""

    charset = (
        message.get_content_charset()
        or "utf-8"
    )

    text = payload.decode(
        charset,
        errors="replace",
    )

    if (
        message.get_content_type()
        == "text/html"
    ):
        return html_to_text(text)

    return text.strip()

def connect_imap() -> imaplib.IMAP4_SSL:
    """Réessaie les coupures transitoires avant toute authentification."""
    context = ssl.create_default_context()
    for attempt in range(3):
        try:
            return imaplib.IMAP4_SSL(
                IMAP_HOST,
                IMAP_PORT,
                ssl_context=context,
                timeout=15,
            )
        except ssl.SSLCertVerificationError:
            raise RuntimeError(
                "Certificat TLS IMAP non valide. Vérifier le nom du serveur, "
                "l'heure système et les certificats de confiance."
            ) from None
        except (ConnectionResetError, TimeoutError, ssl.SSLEOFError):
            if attempt == 2:
                raise RuntimeError(
                    "Connexion IMAP interrompue ou trop lente avant authentification "
                    "après 3 tentatives. Vérifier la disponibilité du serveur "
                    "et le réseau, puis réessayer."
                ) from None
            time.sleep(attempt + 1)
    raise RuntimeError("Connexion IMAP impossible.")


def scan_imap(
    since: datetime,
) -> list[DetectedEmail]:

    detected: list[DetectedEmail] = []

    connection = connect_imap()

    try:
        connection.login(
            IMAP_USERNAME,
            IMAP_PASSWORD,
        )

        status, _ = connection.select(
            IMAP_FOLDER,
            readonly=True,
        )

        if status != "OK":
            raise RuntimeError(
                f"Dossier IMAP inaccessible : "
                f"{IMAP_FOLDER}"
            )

        imap_date = since.strftime(
            "%d-%b-%Y"
        )

        status, data = connection.search(
            None,
            "SINCE",
            imap_date,
        )

        if status != "OK":
            raise RuntimeError(
                "Recherche IMAP impossible."
            )

        message_ids = (
            data[0].split()
            if data and data[0]
            else []
        )

        print()
        print("📨 IMAP")

        total_seen = 0

        for imap_id in message_ids:
            total_seen += 1

            status, raw_data = connection.fetch(
                imap_id,
                "(RFC822)",
            )

            if status != "OK":
                continue

            raw_message = None

            for item in raw_data:
                if (
                    isinstance(item, tuple)
                    and len(item) >= 2
                ):
                    raw_message = item[1]
                    break

            if not raw_message:
                continue

            message = email.message_from_bytes(
                raw_message
            )

            sender = decode_mime_header(
                str(
                    message.get(
                        "From",
                        "",
                    )
                )
            )

            subject = decode_mime_header(
                str(
                    message.get(
                        "Subject",
                        "",
                    )
                )
            )

            message_id = str(
                message.get(
                    "Message-ID",
                    "",
                )
            ).strip()

            if not message_id:
                message_id = (
                    f"imap:{IMAP_HOST}:"
                    f"{imap_id.decode()}"
                )

            body = get_message_body(
                message
            )

            if not should_analyze_email(
                sender,
                subject,
                body,
            ):
                continue

            date_header = str(message.get("Date", ""))

            normalized_message = build_email_message(
                sender=sender,
                subject=subject,
                message_id=message_id,
                body=body,
                date=date_header,
            )

            score, reasons, normalized_body = (
                score_message(
                    normalized_message
                )
            )

            if score < 5:
                continue

            status_value = detect_status(
                subject,
                normalized_body,
            )

            try:
                date = parsedate_to_datetime(date_header)
            except (TypeError, ValueError):
                date = datetime.now().astimezone()
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)

            detected.append(
                DetectedEmail(
                    mailbox=(
                        f"IMAP {IMAP_HOST}"
                    ),
                    date=date,
                    sender=sender,
                    subject=subject,
                    message_id=message_id,
                    score=score,
                    status=status_value,
                    reasons=reasons,
                    body=normalized_body,
                )
            )

        print(
            f"  Parcourus : {total_seen}"
        )

        print(
            f"  Détectés  : {len(detected)}"
        )

    finally:
        try:
            connection.logout()
        except Exception:
            pass

    return detected
