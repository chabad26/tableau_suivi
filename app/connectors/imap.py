from __future__ import annotations

import email
import imaplib
import ssl
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import Message
from email.utils import parsedate_to_datetime

from app.classifier import detect_status, score_message
from app.connectors.common import (
    build_email_message,
    decode_mime_header,
    get_message_html,
    html_to_text,
    sanitize_header_value,
)
from app.mail_filters import should_analyze_email
from app.models import DetectedEmail


class ImapAuthenticationError(Exception):
    pass


@dataclass(frozen=True)
class ImapAccount:
    account_id: int | None
    key: str
    label: str
    provider: str
    host: str
    port: int
    use_ssl: bool
    username: str
    auth_method: str
    password: str | None
    folder: str
    last_uid: int
    uid_validity: int | None


@dataclass(frozen=True)
class ImapScanBatch:
    """Résultat d'un scan accompagné de son checkpoint."""

    emails: list[DetectedEmail]
    last_uid: int
    uid_validity: int | None
    failed_uids: int = 0


def get_message_body(message: Message) -> str:
    if message.is_multipart():
        plain_parts: list[str] = []
        html_parts: list[str] = []

        for part in message.walk():
            disposition = str(part.get("Content-Disposition", "")).casefold()

            if "attachment" in disposition:
                continue

            content_type = part.get_content_type()

            if content_type not in {"text/plain", "text/html"}:
                continue

            payload = part.get_payload(decode=True)

            # get_payload peut aussi renvoyer un Message : decode exige des octets.
            if not isinstance(payload, bytes) or not payload:
                continue

            charset = part.get_content_charset() or "utf-8"

            text = payload.decode(charset, errors="replace")

            if content_type == "text/plain":
                plain_parts.append(text)
            else:
                html_parts.append(text)

        if plain_parts:
            return "\n\n".join(plain_parts).strip()

        if html_parts:
            return html_to_text("\n\n".join(html_parts))

        return ""

    payload = message.get_payload(decode=True)

    if not isinstance(payload, bytes) or not payload:
        return ""

    charset = message.get_content_charset() or "utf-8"

    text = payload.decode(charset, errors="replace")

    if message.get_content_type() == "text/html":
        return html_to_text(text)

    return text.strip()


def connect_imap(account: ImapAccount) -> imaplib.IMAP4:
    for attempt in range(3):
        try:
            if account.use_ssl:
                context = ssl.create_default_context()

                return imaplib.IMAP4_SSL(
                    account.host, account.port, ssl_context=context, timeout=15
                )

            connection = imaplib.IMAP4(account.host, account.port, timeout=15)
            try:
                connection.starttls(ssl_context=ssl.create_default_context())
            except Exception:
                connection.shutdown()
                raise
            return connection

        except ssl.SSLCertVerificationError:
            raise RuntimeError("Certificat TLS IMAP non valide.") from None

        except ConnectionResetError, TimeoutError, ssl.SSLEOFError:
            if attempt == 2:
                raise RuntimeError(
                    "Connexion IMAP interrompue après 3 tentatives."
                ) from None

            time.sleep(attempt + 1)

    raise RuntimeError("Connexion IMAP impossible.")


def scan_imap_account(
    account: ImapAccount,
    since: datetime,
    *,
    authenticator: Callable[[imaplib.IMAP4], None],
) -> ImapScanBatch:
    """Lit une boîte sans modifier SQLite ; le propriétaire valide le checkpoint après import."""
    detected: list[DetectedEmail] = []

    connection = connect_imap(account)

    try:
        try:
            authenticator(connection)

        except imaplib.IMAP4.error as error:
            raise ImapAuthenticationError("Authentification IMAP refusée.") from error

        status, _ = connection.select(account.folder, readonly=True)

        if status != "OK":
            raise RuntimeError("Dossier IMAP inaccessible.")

        # UIDVALIDITY permet de vérifier que les UID mémorisés
        # appartiennent toujours à la même boîte.
        _, uid_validity_data = connection.response("UIDVALIDITY")

        current_uid_validity: int | None = None

        if uid_validity_data and uid_validity_data[0]:
            raw_uid_validity = uid_validity_data[0]

            try:
                if isinstance(raw_uid_validity, bytes):
                    current_uid_validity = int(raw_uid_validity.decode("ascii"))
                else:
                    current_uid_validity = int(raw_uid_validity)

            except ValueError, TypeError:
                current_uid_validity = None

        imap_date = since.strftime("%d-%b-%Y")

        message_ids: list[str] = []

        # Scan incrémental si la boîte n'a pas changé
        # et qu'un UID précédent est connu.
        if (
            current_uid_validity is not None
            and account.uid_validity == current_uid_validity
            and account.last_uid > 0
        ):
            status, data = connection.uid(
                "search",
                None,  # type: ignore[arg-type]
                "UID",
                f"{account.last_uid + 1}:*",
            )

        else:
            # Premier scan ou changement de UIDVALIDITY.
            status, data = connection.uid(
                "search",
                None,  # type: ignore[arg-type]
                "SINCE",
                imap_date,
            )

        if status != "OK":
            raise RuntimeError("Recherche IMAP impossible.")

        # Récupération des UID renvoyés par le serveur.
        if data and data[0]:
            raw_ids = data[0]

            if isinstance(raw_ids, bytes):
                message_ids = raw_ids.decode("ascii", errors="ignore").split()

        # Protection contre les UID déjà traités.
        if (
            current_uid_validity is not None
            and account.uid_validity == current_uid_validity
            and account.last_uid > 0
        ):
            message_ids = [uid for uid in message_ids if int(uid) > account.last_uid]

        print()
        print(f"📨 IMAP — {account.label}")

        total_seen = 0
        failed_uids: list[int] = []

        for imap_uid in message_ids:
            total_seen += 1

            try:
                status, raw_data = connection.uid("fetch", imap_uid, "(BODY.PEEK[])")

                if status != "OK":
                    failed_uids.append(int(imap_uid))
                    continue

                raw_message: bytes | None = None

                for item in raw_data:
                    if (
                        isinstance(item, tuple)
                        and len(item) >= 2
                        and isinstance(item[1], bytes)
                    ):
                        raw_message = item[1]
                        break

                if not raw_message:
                    failed_uids.append(int(imap_uid))
                    continue

                message = email.message_from_bytes(raw_message)

                sender = decode_mime_header(str(message.get("From", "")))

                subject = decode_mime_header(str(message.get("Subject", "")))

                date_header = str(message.get("Date", ""))

                try:
                    date = parsedate_to_datetime(date_header)

                except TypeError, ValueError:
                    date = datetime.now(timezone.utc)

                if date.tzinfo is None:
                    date = date.replace(tzinfo=timezone.utc)

                if date.astimezone(timezone.utc) < since.astimezone(timezone.utc):
                    continue

                message_id = str(message.get("Message-ID", "")).strip()

                if not message_id:
                    message_id = f"imap:{account.key}:{imap_uid}"

                body = get_message_body(message)

                if not should_analyze_email(sender, subject, body):
                    continue

                sender = sanitize_header_value(sender)

                subject = sanitize_header_value(subject)

                message_id = sanitize_header_value(message_id)

                date_header = sanitize_header_value(date_header)

                normalized_message = build_email_message(
                    sender=sender,
                    subject=subject,
                    message_id=message_id,
                    body=body,
                    date=date_header,
                )

                (score, reasons, normalized_body) = score_message(normalized_message)

                if score < 5:
                    continue

                status_value = detect_status(subject, normalized_body)

                detected.append(
                    DetectedEmail(
                        mailbox=account.label,
                        date=date,
                        sender=sender,
                        subject=subject,
                        message_id=message_id,
                        score=score,
                        status=status_value,
                        reasons=reasons,
                        body=normalized_body,
                        html_body=get_message_html(message),
                        in_reply_to=sanitize_header_value(
                            str(message.get("In-Reply-To", ""))[-8192:]
                        ),
                        references=sanitize_header_value(
                            str(message.get("References", ""))[-8192:]
                        ),
                    )
                )

            except Exception as error:
                failed_uids.append(int(imap_uid))
                print(f"  ⚠ UID {imap_uid} ignoré ({type(error).__name__})")
                continue

        searched_uids = [int(imap_uid) for imap_uid in message_ids]

        same_uid_validity = (
            current_uid_validity is not None
            and account.uid_validity == current_uid_validity
        )

        minimum_uid = account.last_uid if same_uid_validity else 0

        if searched_uids:
            max_uid = max(searched_uids)
        else:
            max_uid = minimum_uid

        if failed_uids:
            first_failed_uid = min(failed_uids)

            max_uid = min(max_uid, first_failed_uid - 1)

        max_uid = max(max_uid, minimum_uid)

        print(f"  Détectés  : {len(detected)}")

        print(f"  Parcourus : {total_seen}")

    finally:
        try:
            connection.logout()
        except Exception:
            pass

    return ImapScanBatch(
        emails=detected,
        last_uid=max_uid,
        uid_validity=current_uid_validity,
        failed_uids=len(failed_uids),
    )
